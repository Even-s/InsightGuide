import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { sessionsAPI, type SessionWithDeck } from '@/api/sessions';
import SessionStats from '@/components/sessions/SessionStats';
import SessionFilters from '@/components/sessions/SessionFilters';
import SessionTable from '@/components/sessions/SessionTable';

export default function SessionListPage() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionWithDeck[]>([]);
  const [filteredSessions, setFilteredSessions] = useState<SessionWithDeck[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'createdAt' | 'startedAt' | 'endedAt' | 'status'>('createdAt');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [currentPage, setCurrentPage] = useState(0);
  const [pageSize] = useState(20);

  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    ended: 0,
    avgDuration: 0,
  });

  const loadSessions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await sessionsAPI.listSessions({
        limit: 1000,
        offset: 0,
        sortBy,
        order: sortOrder,
      });
      setSessions(response.sessions);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sessions');
    } finally {
      setLoading(false);
    }
  }, [sortBy, sortOrder]);

  const loadStats = useCallback(async () => {
    try {
      const statsData = await sessionsAPI.getSessionStats();
      setStats(statsData);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }, []);

  const applyFilters = useCallback(() => {
    let filtered = [...sessions];

    if (statusFilter !== 'all') {
      filtered = filtered.filter((s) => s.status === statusFilter);
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter((s) =>
        s.deckTitle.toLowerCase().includes(query)
      );
    }

    filtered.sort((a, b) => {
      const aValue = a[sortBy];
      const bValue = b[sortBy];

      if (!aValue && !bValue) return 0;
      if (!aValue) return sortOrder === 'asc' ? 1 : -1;
      if (!bValue) return sortOrder === 'asc' ? -1 : 1;

      if (typeof aValue === 'string' && typeof bValue === 'string') {
        const comparison = aValue.localeCompare(bValue);
        return sortOrder === 'asc' ? comparison : -comparison;
      }

      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return sortOrder === 'asc' ? aValue - bValue : bValue - aValue;
      }

      return 0;
    });

    setFilteredSessions(filtered);
    setCurrentPage(0);
  }, [searchQuery, sessions, sortBy, sortOrder, statusFilter]);

  useEffect(() => {
    loadSessions();
    loadStats();
  }, [loadSessions, loadStats]);

  useEffect(() => {
    applyFilters();
  }, [applyFilters]);

  const handleDelete = async (sessionId: string) => {
    try {
      await sessionsAPI.deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      loadStats();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete session');
    }
  };

  const handleSort = (field: 'createdAt' | 'startedAt' | 'endedAt' | 'status') => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const paginatedSessions = filteredSessions.slice(
    currentPage * pageSize,
    (currentPage + 1) * pageSize
  );

  const totalPages = Math.ceil(filteredSessions.length / pageSize);

  if (loading) {
    return (
      <div className="min-h-screen bg-cream-100 flex items-center justify-center">
        <div className="text-natural-600">Loading sessions...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-cream-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-medium text-natural-700 tracking-wide">Presentation Sessions</h1>
            <p className="text-natural-600 mt-1">View and manage all presentation sessions</p>
          </div>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-sage-400 text-white rounded-xl hover:bg-sage-500 shadow-natural font-medium tracking-wide"
          >
            Back to Home
          </button>
        </div>

        {error && (
          <div className="bg-wood-50 border border-wood-300 text-wood-600 px-4 py-3 rounded-xl mb-6">
            {error}
          </div>
        )}

        <SessionStats
          total={stats.total}
          active={stats.active}
          ended={stats.ended}
          avgDuration={stats.avgDuration}
        />

        <SessionFilters
          statusFilter={statusFilter}
          onStatusChange={setStatusFilter}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

        <SessionTable
          sessions={paginatedSessions}
          onDelete={handleDelete}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSort={handleSort}
        />

        {totalPages > 1 && (
          <div className="mt-6 flex justify-center items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
              disabled={currentPage === 0}
              className="px-4 py-2 bg-cream-50 border border-cream-300 rounded-xl text-sm font-medium text-natural-700 hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed shadow-natural tracking-wide"
            >
              Previous
            </button>
            <span className="text-sm text-natural-700">
              Page {currentPage + 1} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={currentPage >= totalPages - 1}
              className="px-4 py-2 bg-cream-50 border border-cream-300 rounded-xl text-sm font-medium text-natural-700 hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed shadow-natural tracking-wide"
            >
              Next
            </button>
          </div>
        )}

        {filteredSessions.length > 0 && (
          <div className="mt-4 text-center text-sm text-natural-500">
            Showing {paginatedSessions.length} of {filteredSessions.length} sessions
          </div>
        )}
      </div>
    </div>
  );
}
