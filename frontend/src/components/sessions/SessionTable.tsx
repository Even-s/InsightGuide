import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { SessionWithDeck } from '@/api/sessions';
import { formatDateTime, formatDuration, formatTokenCount, formatUsdCost } from '@/utils/formatters';

interface SessionTableProps {
  sessions: SessionWithDeck[];
  onDelete: (sessionId: string) => void;
  sortBy: 'createdAt' | 'startedAt' | 'endedAt' | 'status';
  sortOrder: 'asc' | 'desc';
  onSort: (field: 'createdAt' | 'startedAt' | 'endedAt' | 'status') => void;
}

export default function SessionTable({
  sessions,
  onDelete,
  sortBy,
  sortOrder,
  onSort,
}: SessionTableProps) {
  const navigate = useNavigate();
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const handleDelete = (sessionId: string) => {
    if (deleteConfirm === sessionId) {
      onDelete(sessionId);
      setDeleteConfirm(null);
    } else {
      setDeleteConfirm(sessionId);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'interviewing':
        return 'bg-sage-200 text-sage-700';
      case 'paused':
        return 'bg-wood-100 text-wood-600';
      case 'ended':
        return 'bg-cream-200 text-natural-700';
      case 'idle':
        return 'bg-sage-100 text-sage-600';
      case 'failed':
        return 'bg-wood-200 text-wood-600';
      default:
        return 'bg-cream-200 text-natural-700';
    }
  };

  const SortIcon = ({ field }: { field: string }) => {
    if (sortBy !== field) {
      return (
        <svg className="w-4 h-4 ml-1 text-natural-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      );
    }
    return sortOrder === 'asc' ? (
      <svg className="w-4 h-4 ml-1 text-sage-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
      </svg>
    ) : (
      <svg className="w-4 h-4 ml-1 text-sage-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    );
  };

  return (
    <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-cream-300">
          <thead className="bg-wood-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider">
                Session ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider">
                Deck Title
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider cursor-pointer hover:bg-cream-100"
                onClick={() => onSort('status')}
              >
                <div className="flex items-center">
                  Status
                  <SortIcon field="status" />
                </div>
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider cursor-pointer hover:bg-cream-100"
                onClick={() => onSort('startedAt')}
              >
                <div className="flex items-center">
                  Started At
                  <SortIcon field="startedAt" />
                </div>
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider cursor-pointer hover:bg-cream-100"
                onClick={() => onSort('endedAt')}
              >
                <div className="flex items-center">
                  Ended At
                  <SortIcon field="endedAt" />
                </div>
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider">
                Duration
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider">
                AI Cost
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-natural-600 uppercase tracking-wider cursor-pointer hover:bg-cream-100"
                onClick={() => onSort('createdAt')}
              >
                <div className="flex items-center">
                  Created At
                  <SortIcon field="createdAt" />
                </div>
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-natural-600 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-cream-200">
            {sessions.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-6 py-12 text-center text-natural-500">
                  No sessions found
                </td>
              </tr>
            ) : (
              sessions.map((session) => (
                <tr key={session.id} className="hover:bg-cream-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-natural-700">
                    {session.id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-natural-700">
                    {session.deckTitle}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2 py-1 inline-flex text-xs leading-5 font-medium rounded-lg ${getStatusBadgeClass(
                        session.status
                      )}`}
                    >
                      {session.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-natural-600">
                    {formatDateTime(session.startedAt)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-natural-600">
                    {formatDateTime(session.endedAt)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-natural-700">
                    {session.duration ? formatDuration(session.duration) : 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-natural-700">
                    <div className="font-medium">{formatUsdCost(session.costUsd)}</div>
                    <div className="text-xs text-natural-500">
                      {formatTokenCount(session.aiUsage?.totalTokens)} tokens
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-natural-600">
                    {formatDateTime(session.createdAt)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => navigate(`/editor/${session.deckId}`)}
                        className="text-sage-600 hover:text-sage-700 font-medium"
                        title="View details"
                      >
                        View
                      </button>
                      <button
                        onClick={() => handleDelete(session.id)}
                        className={`${
                          deleteConfirm === session.id
                            ? 'text-wood-600 hover:text-wood-700 font-semibold'
                            : 'text-wood-500 hover:text-wood-600'
                        }`}
                        title={deleteConfirm === session.id ? 'Click again to confirm' : 'Delete session'}
                      >
                        {deleteConfirm === session.id ? 'Confirm?' : 'Delete'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
