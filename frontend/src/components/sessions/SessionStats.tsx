import { formatDuration } from '@/utils/formatters';

interface SessionStatsProps {
  total: number;
  active: number;
  ended: number;
  avgDuration: number;
}

export default function SessionStats({ total, active, ended, avgDuration }: SessionStatsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 p-6">
        <div className="text-sm font-medium text-natural-500 tracking-wide">Total Sessions</div>
        <div className="mt-2 text-3xl font-medium text-natural-700">{total}</div>
      </div>

      <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 p-6">
        <div className="text-sm font-medium text-natural-500 tracking-wide">Active Sessions</div>
        <div className="mt-2 text-3xl font-medium text-sage-600">{active}</div>
      </div>

      <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 p-6">
        <div className="text-sm font-medium text-natural-500 tracking-wide">Ended Sessions</div>
        <div className="mt-2 text-3xl font-medium text-natural-600">{ended}</div>
      </div>

      <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 p-6">
        <div className="text-sm font-medium text-natural-500 tracking-wide">Avg Duration</div>
        <div className="mt-2 text-3xl font-medium text-sage-600">
          {formatDuration(avgDuration)}
        </div>
      </div>
    </div>
  );
}
