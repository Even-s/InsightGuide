interface SessionFiltersProps {
  statusFilter: string;
  onStatusChange: (status: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export default function SessionFilters({
  statusFilter,
  onStatusChange,
  searchQuery,
  onSearchChange,
}: SessionFiltersProps) {
  return (
    <div className="bg-cream-50 rounded-xl shadow-natural border border-cream-300 p-4 mb-6">
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1">
          <label htmlFor="search" className="block text-sm font-medium text-natural-700 mb-1 tracking-wide">
            Search by Deck
          </label>
          <input
            id="search"
            type="text"
            placeholder="Search deck title..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full px-3 py-2 border border-cream-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-sage-300 bg-white text-natural-700"
          />
        </div>

        <div className="w-full md:w-48">
          <label htmlFor="status" className="block text-sm font-medium text-natural-700 mb-1 tracking-wide">
            Status
          </label>
          <select
            id="status"
            value={statusFilter}
            onChange={(e) => onStatusChange(e.target.value)}
            className="w-full px-3 py-2 border border-cream-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-sage-300 bg-white text-natural-700"
          >
            <option value="all">All Statuses</option>
            <option value="idle">Idle</option>
            <option value="preparing">Preparing</option>
            <option value="ready">Ready</option>
            <option value="presenting">Presenting</option>
            <option value="paused">Paused</option>
            <option value="ended">Ended</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>
    </div>
  );
}
