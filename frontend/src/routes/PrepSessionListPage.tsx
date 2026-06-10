import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { prepSessionsAPI, type PrepSessionWithDeck, type PresentationSessionForPrep } from '@/api/prepSessions';
import { formatDateUTC } from '@/utils/dateUtils';
import { formatTokenCount, formatUsdCost } from '@/utils/formatters';

// Icon components
function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  );
}


function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}

export default function PrepSessionListPage() {
  const navigate = useNavigate();
  const [prepSessions, setPrepSessions] = useState<PrepSessionWithDeck[]>([]);
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(new Set());
  const [presentationSessions, setPresentationSessions] = useState<Record<string, PresentationSessionForPrep[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'createdAt' | 'updatedAt' | 'status'>('createdAt');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const [stats, setStats] = useState({
    total: 0,
    preparing: 0,
    ready: 0,
    archived: 0,
    totalPresentationSessions: 0,
  });

  const loadPrepSessions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await prepSessionsAPI.listPrepSessions({
        limit: 1000,
        offset: 0,
        sortBy,
        order: sortOrder,
      });
      setPrepSessions(response.prepSessions);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load prep sessions');
    } finally {
      setLoading(false);
    }
  }, [sortBy, sortOrder]);

  const loadStats = useCallback(async () => {
    try {
      const statsData = await prepSessionsAPI.getPrepSessionStats();
      setStats(statsData);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }, []);

  const preparingPrepSessionIds = useMemo(
    () => prepSessions
      .filter((prepSession) => prepSession.status === 'preparing')
      .map((prepSession) => prepSession.id)
      .join(','),
    [prepSessions],
  );

  useEffect(() => {
    loadPrepSessions();
    loadStats();
  }, [loadPrepSessions, loadStats]);

  // Global event listener for prep session creation/deletion
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001';
    const url = `${apiUrl}/api/prep-sessions/events`;
    const eventSource = new EventSource(url);

    eventSource.addEventListener('connected', () => {
      console.log('✅ Connected to global prep sessions events');
    });

    eventSource.addEventListener('PREP_SESSION_CREATED', (e) => {
      const event = JSON.parse(e.data);
      console.log('📥 New prep session created:', event);

      // Reload the list to include the new prep session
      loadPrepSessions();
      loadStats();
    });

    eventSource.addEventListener('PREP_SESSION_DELETED', (e) => {
      const event = JSON.parse(e.data);
      console.log('📥 Prep session deleted:', event);

      // Remove from local state
      setPrepSessions(prev => prev.filter(ps => ps.id !== event.prepSessionId));
      loadStats();
    });

    eventSource.addEventListener('error', (e) => {
      console.error('❌ Global prep sessions SSE error:', e);
    });

    return () => {
      console.log('🔌 Disconnecting from global prep sessions events');
      eventSource.close();
    };
  }, [loadPrepSessions, loadStats]);

  // Handle real-time status updates for ALL prep sessions
  // We'll connect to each one and update state when status changes
  useEffect(() => {
    const eventSources: EventSource[] = [];

    prepSessions.forEach(ps => {
      // Only subscribe to preparing sessions
      if (ps.status !== 'preparing') return;

      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const url = `${apiUrl}/api/prep-sessions/${ps.id}/events`;
      const eventSource = new EventSource(url);

      eventSource.addEventListener('PREP_STATUS_CHANGED', (e) => {
        const event = JSON.parse(e.data);
        console.log(`Prep session ${event.prepSessionId} status changed to ${event.status}`);

        // Update the prep session in the list
        setPrepSessions(prev => prev.map(session =>
          session.id === event.prepSessionId
            ? { ...session, status: event.status, updatedAt: event.timestamp }
            : session
        ));

        // Reload stats
        loadStats();
      });

      eventSource.addEventListener('error', () => {
        console.error(`SSE error for prep session ${ps.id}`);
      });

      eventSources.push(eventSource);
    });

    // Cleanup on unmount or when prepSessions change
    return () => {
      eventSources.forEach(es => es.close());
    };
  }, [loadStats, prepSessions, preparingPrepSessionIds]);

  const toggleExpanded = async (prepSessionId: string) => {
    const newExpanded = new Set(expandedSessions);

    if (newExpanded.has(prepSessionId)) {
      newExpanded.delete(prepSessionId);
    } else {
      newExpanded.add(prepSessionId);

      // Load presentation sessions if not already loaded
      if (!presentationSessions[prepSessionId]) {
        try {
          const sessions = await prepSessionsAPI.getPrepSessionPresentationSessions(prepSessionId);
          setPresentationSessions(prev => ({
            ...prev,
            [prepSessionId]: sessions
          }));
        } catch (err) {
          console.error('Failed to load presentation sessions:', err);
        }
      }
    }

    setExpandedSessions(newExpanded);
  };

  const handleDeletePrepSession = async (prepSessionId: string, deckTitle: string) => {
    const message = `⚠️ WARNING: This will permanently delete:\n\n` +
      `• The deck "${deckTitle}"\n` +
      `• All slides and topic cards\n` +
      `• All presentation sessions\n` +
      `• All related data\n\n` +
      `This action CANNOT be undone.\n\n` +
      `Are you sure you want to delete this prep session?`;

    if (!confirm(message)) {
      return;
    }

    try {
      await prepSessionsAPI.deletePrepSession(prepSessionId);
      setPrepSessions(prev => prev.filter(s => s.id !== prepSessionId));
      loadStats();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete prep session');
    }
  };

  const handleDeleteAll = async () => {
    const confirmMessage = `⚠️ WARNING: This will permanently delete ALL ${stats.total} prep sessions and ${stats.totalPresentationSessions} presentation sessions!\n\nThis action CANNOT be undone.\n\nType "DELETE ALL" to confirm:`;
    const userInput = prompt(confirmMessage);

    if (userInput !== 'DELETE ALL') {
      return;
    }

    try {
      setLoading(true);
      await prepSessionsAPI.deleteAllPrepSessions();
      setPrepSessions([]);
      setPresentationSessions({});
      setExpandedSessions(new Set());
      await loadStats();
      alert('All prep sessions deleted successfully');
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete all prep sessions');
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (field: 'createdAt' | 'updatedAt' | 'status') => {
    if (sortBy === field) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case 'preparing':
        return 'bg-wood-100 text-wood-600';
      case 'ready':
        return 'bg-sage-200 text-sage-700';
      case 'archived':
        return 'bg-cream-200 text-natural-700';
      case 'presenting':
        return 'bg-sage-100 text-sage-600';
      case 'ended':
        return 'bg-cream-200 text-natural-600';
      default:
        return 'bg-cream-200 text-natural-700';
    }
  };

  // Use formatDateUTC from dateUtils for proper timezone handling
  const formatDate = formatDateUTC;

  const formatDuration = (startedAt?: string, endedAt?: string) => {
    if (!startedAt || !endedAt) return '-';
    const duration = Math.floor((new Date(endedAt).getTime() - new Date(startedAt).getTime()) / 1000);
    const minutes = Math.floor(duration / 60);
    const seconds = duration % 60;
    return `${minutes}m ${seconds}s`;
  };

  const filteredPrepSessions = prepSessions.filter(ps => {
    if (statusFilter !== 'all' && ps.status !== statusFilter) {
      return false;
    }
    if (searchQuery && !ps.deckTitle.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-cream-100 flex items-center justify-center">
        <div className="text-natural-600">Loading prep sessions...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-cream-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-medium text-natural-700 tracking-wide">Prep Sessions</h1>
            <p className="text-natural-600 mt-1">Manage your presentation preparation sessions</p>
          </div>
          <div className="flex gap-3">
            {stats.total > 0 && (
              <button
                onClick={handleDeleteAll}
                className="px-4 py-2 bg-wood-400 text-white rounded-xl hover:bg-wood-500 shadow-natural flex items-center gap-2 font-medium tracking-wide"
                title="Delete all prep sessions and presentation sessions"
              >
                <TrashIcon className="w-4 h-4" />
                Delete All ({stats.total})
              </button>
            )}
            <button
              onClick={() => navigate('/')}
              className="px-4 py-2 bg-sage-400 text-white rounded-xl hover:bg-sage-500 shadow-natural font-medium tracking-wide"
            >
              Back to Home
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-wood-50 border border-wood-300 text-wood-600 px-4 py-3 rounded-xl mb-6">
            {error}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
          <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 p-4">
            <div className="text-sm text-natural-600 tracking-wide">Total Prep Sessions</div>
            <div className="text-2xl font-medium text-natural-700">{stats.total}</div>
          </div>
          <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 p-4">
            <div className="text-sm text-natural-600 tracking-wide">Preparing</div>
            <div className="text-2xl font-medium text-wood-600">{stats.preparing}</div>
          </div>
          <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 p-4">
            <div className="text-sm text-natural-600 tracking-wide">Ready</div>
            <div className="text-2xl font-medium text-sage-600">{stats.ready}</div>
          </div>
          <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 p-4">
            <div className="text-sm text-natural-600 tracking-wide">Archived</div>
            <div className="text-2xl font-medium text-natural-600">{stats.archived}</div>
          </div>
          <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 p-4">
            <div className="text-sm text-natural-600 tracking-wide">Total Presentations</div>
            <div className="text-2xl font-medium text-sage-600">{stats.totalPresentationSessions}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-natural-700 mb-2 tracking-wide">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-full px-3 py-2 border border-cream-300 rounded-xl focus:ring-2 focus:ring-sage-300 bg-white text-natural-700"
              >
                <option value="all">All Statuses</option>
                <option value="preparing">Preparing</option>
                <option value="ready">Ready</option>
                <option value="archived">Archived</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-natural-700 mb-2 tracking-wide">Search</label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by deck title..."
                className="w-full px-3 py-2 border border-cream-300 rounded-xl focus:ring-2 focus:ring-sage-300 bg-white text-natural-700"
              />
            </div>
          </div>
        </div>

        {/* Prep Sessions Table */}
        <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 overflow-hidden">
          <table className="min-w-full divide-y divide-cream-300">
            <thead className="bg-wood-50">
              <tr>
                <th className="w-12 px-6 py-3"></th>
                <th className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider">
                  ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider">
                  Deck / Title
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider">
                  Presentations
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider">
                  Deck AI Cost
                </th>
                <th
                  className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider cursor-pointer hover:bg-cream-100"
                  onClick={() => handleSort('createdAt')}
                >
                  Created {sortBy === 'createdAt' && (sortOrder === 'asc' ? '↑' : '↓')}
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-natural-600 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-cream-200">
              {filteredPrepSessions.map((prepSession) => (
                <>
                  <tr key={prepSession.id} className="hover:bg-cream-50">
                    <td className="px-6 py-4">
                      <button
                        onClick={() => toggleExpanded(prepSession.id)}
                        className="text-natural-400 hover:text-natural-600"
                      >
                        {expandedSessions.has(prepSession.id) ? (
                          <ChevronDownIcon className="w-5 h-5" />
                        ) : (
                          <ChevronRightIcon className="w-5 h-5" />
                        )}
                      </button>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-xs font-mono text-natural-500">{prepSession.id}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-natural-700">{prepSession.deckTitle}</div>
                      {prepSession.title && (
                        <div className="text-sm text-natural-600">{prepSession.title}</div>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 inline-flex text-xs leading-5 font-medium rounded-lg ${getStatusBadgeColor(prepSession.status)}`}>
                        {prepSession.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-natural-700">
                      {prepSession.presentationSessionsCount}
                    </td>
                    <td className="px-6 py-4 text-sm text-natural-700">
                      <div className="font-medium">{formatUsdCost(prepSession.deckCostUsd)}</div>
                      <div className="text-xs text-natural-500">
                        {formatTokenCount(prepSession.deckAiUsage?.totalTokens)} tokens
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-natural-600">
                      {formatDate(prepSession.createdAt)}
                    </td>
                    <td className="px-6 py-4 text-right text-sm font-medium">
                      <button
                        onClick={() => handleDeletePrepSession(prepSession.id, prepSession.deckTitle)}
                        className="text-wood-500 hover:text-wood-600 ml-4"
                        title="Delete prep session and deck"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>

                  {/* Expanded Presentation Sessions */}
                  {expandedSessions.has(prepSession.id) && (
                    <tr>
                      <td colSpan={8} className="px-6 py-4 bg-cream-50">
                        <div className="ml-8">
                          <h4 className="text-sm font-medium text-natural-700 mb-2 tracking-wide">Presentation Sessions</h4>
                          {presentationSessions[prepSession.id]?.length > 0 ? (
                            <table className="min-w-full">
                              <thead>
                                <tr className="text-xs text-natural-600">
                                  <th className="text-left py-2">ID</th>
                                  <th className="text-left py-2">Status</th>
                                  <th className="text-left py-2">Started</th>
                                  <th className="text-left py-2">Ended</th>
                                  <th className="text-left py-2">Duration</th>
                                  <th className="text-left py-2">AI Cost</th>
                                </tr>
                              </thead>
                              <tbody>
                                {presentationSessions[prepSession.id].map((session) => (
                                  <tr key={session.id} className="text-sm">
                                    <td className="py-2">
                                      <div className="text-xs font-mono text-gray-500">{session.id}</div>
                                    </td>
                                    <td className="py-2">
                                      <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusBadgeColor(session.status)}`}>
                                        {session.status}
                                      </span>
                                    </td>
                                    <td className="py-2 text-natural-600">
                                      {session.startedAt ? formatDate(session.startedAt) : '-'}
                                    </td>
                                    <td className="py-2 text-natural-600">
                                      {session.endedAt ? formatDate(session.endedAt) : '-'}
                                    </td>
                                    <td className="py-2 text-natural-600">
                                      {formatDuration(session.startedAt, session.endedAt)}
                                    </td>
                                    <td className="py-2 text-natural-700">
                                      <div className="font-medium">{formatUsdCost(session.costUsd)}</div>
                                      <div className="text-xs text-natural-500">
                                        {formatTokenCount(session.aiUsage?.totalTokens)} tokens
                                      </div>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          ) : (
                            <p className="text-sm text-natural-500">No presentation sessions yet</p>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>

          {filteredPrepSessions.length === 0 && (
            <div className="text-center py-12 text-natural-500">
              No prep sessions found
            </div>
          )}
        </div>

        <div className="mt-4 text-center text-sm text-natural-500">
          Showing {filteredPrepSessions.length} of {prepSessions.length} prep sessions
        </div>
      </div>
    </div>
  );
}
