# Session Management Architecture

## Component Hierarchy

```
App.tsx
└── Route: /sessions
    └── SessionListPage
        ├── SessionStats
        │   └── Display: total, active, ended, avgDuration
        ├── SessionFilters
        │   ├── Status dropdown
        │   └── Search input
        └── SessionTable
            ├── Sortable column headers
            ├── Session rows
            │   └── Actions: View, Delete
            └── Pagination controls
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  SessionListPage                                                 │
│    │                                                              │
│    ├─► sessionsAPI.listSessions()  ─────────┐                   │
│    │                                          │                   │
│    ├─► sessionsAPI.getSessionStats() ────┐  │                   │
│    │                                       │  │                   │
│    └─► sessionsAPI.deleteSession()  ───┐ │  │                   │
│                                         │ │  │                   │
└─────────────────────────────────────────┼─┼──┼───────────────────┘
                                          │ │  │
                                     HTTP │ │  │ Requests
                                          ▼ ▼  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  /api/presentation-sessions/                                     │
│    │                                                              │
│    ├─► GET    /           ─────────┐                            │
│    │                                 │                            │
│    ├─► GET    /{id}                 │                            │
│    │                                 │                            │
│    ├─► DELETE /{id}  ──────┐       │                            │
│    │                         │       │                            │
│    └─► POST   /              │       │                            │
│                              ▼       ▼                            │
│                        presentation_service                       │
│                              │       │                            │
│                              ├─► list_sessions()                 │
│                              │       │                            │
│                              └─► delete_session()                │
│                                      │                            │
└──────────────────────────────────────┼────────────────────────────┘
                                       │
                                   Database
                                   Queries
                                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database (PostgreSQL)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  presentation_sessions                                           │
│    ├─► id, deck_id, user_id, status                            │
│    ├─► started_at, ended_at, created_at                        │
│    │                                                              │
│    └─► Relationships (CASCADE DELETE):                          │
│        ├─► presentation_card_states                             │
│        └─► utterances                                            │
│                                                                   │
│  decks                                                           │
│    └─► id, title (joined for list query)                        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## API Endpoints

### GET /api/presentation-sessions/

**Request Query Parameters:**
```typescript
{
  status?: string,           // Filter: 'idle', 'presenting', 'ended', etc.
  deckId?: string,          // Filter: specific deck ID
  limit?: number,           // Pagination: 1-100 (default 50)
  offset?: number,          // Pagination: skip N records
  sortBy?: string,          // Sort field: 'createdAt', 'startedAt', etc.
  order?: 'asc' | 'desc'    // Sort order (default 'desc')
}
```

**Response:**
```typescript
{
  sessions: SessionWithDeck[],  // Array of session objects
  total: number,                // Total matching sessions
  limit: number,                // Requested limit
  offset: number                // Requested offset
}
```

**SessionWithDeck Schema:**
```typescript
{
  id: string,
  deckId: string,
  deckTitle: string,         // Joined from decks table
  userId: string,
  status: SessionStatus,
  currentSlideId?: string,
  startedAt?: string,        // ISO datetime
  endedAt?: string,          // ISO datetime
  createdAt: string,         // ISO datetime
  duration?: number          // Computed: seconds between start and end
}
```

### DELETE /api/presentation-sessions/{session_id}

**Response:** 204 No Content

**Cascade Deletes:**
- All `presentation_card_states` for this session
- All `utterances` for this session

## State Management

### SessionListPage State

```typescript
// Data
sessions: SessionWithDeck[]           // All sessions from API
filteredSessions: SessionWithDeck[]   // After filters applied
stats: { total, active, ended, avgDuration }

// UI State
loading: boolean
error: string | null

// Filter State
statusFilter: string                  // 'all' or specific status
searchQuery: string                   // Deck title search

// Sort State
sortBy: 'createdAt' | 'startedAt' | 'endedAt' | 'status'
sortOrder: 'asc' | 'desc'

// Pagination State
currentPage: number
pageSize: number (fixed at 20)
```

## Frontend Filtering Strategy

**Why Client-Side?**
- Responsive UI without API round-trips
- Better UX for small-to-medium datasets (< 1000 sessions)
- Enables instant sorting and search feedback

**Process:**
1. Fetch all sessions once on mount
2. Apply filters/sort locally in `applyFilters()`
3. Paginate filtered results
4. Only refetch on delete or explicit refresh

**Future Optimization:**
For large datasets (10k+ sessions), move filtering to backend with indexed database queries.

## Component Responsibilities

### SessionListPage
- Data fetching and state management
- Orchestrates all child components
- Handles API calls and error states
- Implements filtering, sorting, pagination logic

### SessionStats
- Pure presentational component
- Receives computed stats as props
- Displays four key metrics in grid layout

### SessionFilters
- Controlled inputs for status and search
- Calls parent callbacks on change
- No internal state

### SessionTable
- Renders table with sessions data
- Sortable column headers with visual indicators
- Row actions: View (navigate) and Delete (with confirmation)
- Confirmation pattern: click once to arm, click again within 3s to confirm

## Security Considerations

### Backend
- Session deletion requires valid session_id (404 if not found)
- Future: Add user authentication check (can only delete own sessions)
- SQL injection protected by SQLAlchemy ORM

### Frontend
- API client includes auth token interceptor (ready for auth)
- Delete confirmation prevents accidental deletions
- Client-side validation for pagination params

## Performance Considerations

### Backend
- Database indexes on:
  - `presentation_sessions.status`
  - `presentation_sessions.deck_id`
  - `presentation_sessions.created_at`
- JOIN with decks table is efficient (FK indexed)
- Pagination limits result set size

### Frontend
- Single API call fetches all sessions (trade-off for responsiveness)
- Client-side operations (filter/sort) are fast for < 1000 records
- Memoization opportunity: React.useMemo for filtered results
- Virtual scrolling could be added for 10k+ sessions

## Extension Points

### Backend
```python
# Easy to add new filters
if user_id:
    query = query.filter(PresentationSession.user_id == user_id)

# Easy to add new sort fields
field_map = {
    "duration": "ended_at - started_at",  # Computed field
    "deckTitle": Deck.title
}
```

### Frontend
```typescript
// Easy to add new columns to table
const columns = [
  { key: 'id', label: 'Session ID', sortable: false },
  { key: 'status', label: 'Status', sortable: true },
  // Add more columns here
]

// Easy to add new filters
<select onChange={(e) => setUserFilter(e.target.value)}>
  <option value="all">All Users</option>
  {/* User options */}
</select>
```

## Testing Strategy

### Backend Tests
- List empty sessions (boundary case)
- Pagination parameters respected
- Status filtering works correctly
- Delete nonexistent session returns 404
- Delete cascades to related records

### Frontend Tests (Future)
- Component rendering with mock data
- Filter interactions update displayed sessions
- Sort changes order correctly
- Delete confirmation flow
- Pagination navigation

## Deployment Checklist

- [ ] Backend API deployed with new endpoints
- [ ] Database migrations applied (if schema changed)
- [ ] Frontend build includes new route
- [ ] Navigation updated (home page link)
- [ ] API base URL configured for environment
- [ ] Error tracking enabled for new components
- [ ] Performance monitoring for list endpoint
- [ ] Documentation updated

## Troubleshooting

### "No sessions found" but database has sessions
- Check status filter is set to "All Statuses"
- Clear search query
- Verify API connection (check browser console)

### Delete doesn't work
- Check if session exists (might be already deleted)
- Verify API returns 204 (check Network tab)
- Check for JavaScript errors in console

### Slow loading
- Check number of sessions (> 1000?)
- Consider server-side filtering/pagination
- Check database indexes
- Monitor API response time

### Sort not working
- Check sortBy and sortOrder state
- Verify field names match SessionWithDeck schema
- Check for null/undefined values in sort field
