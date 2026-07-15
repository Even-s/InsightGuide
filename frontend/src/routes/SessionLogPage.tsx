import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiClient } from '@/api/client'

interface LogEvent {
  type: 'session' | 'utterance' | 'card_update' | 'ai_usage'
  timestamp: string
  // session
  action?: string
  // utterance
  transcript?: string
  // card_update
  cardId?: string
  status?: string
  confidence?: number | null
  evidenceTranscript?: string | null
  // ai_usage
  operation?: string
  model?: string
  totalTokens?: number
  costUsd?: number
}

interface SessionLog {
  sessionId: string
  status: string
  startedAt: string | null
  endedAt: string | null
  events: LogEvent[]
}

export default function SessionLogPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [log, setLog] = useState<SessionLog | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('all')

  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    apiClient
      .get(`/api/interview-sessions/${sessionId}/log`)
      .then((r) => setLog(r.data))
      .catch((err) => setError(err?.response?.data?.detail || 'Failed to load session log'))
      .finally(() => setLoading(false))
  }, [sessionId])

  const filteredEvents = log?.events.filter((e) => filter === 'all' || e.type === filter) ?? []

  const formatTime = (ts: string) => {
    const d = new Date(ts)
    return d.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  const formatDate = (ts: string | null) => {
    if (!ts) return 'N/A'
    return new Date(ts).toLocaleString('zh-TW')
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-cream-100 flex items-center justify-center">
        <div className="text-natural-600">Loading session log...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-cream-100 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-3">{error}</p>
          <button onClick={() => navigate('/prep-sessions')} className="text-sage-600 hover:underline">
            Back to Sessions
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-cream-100">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-medium text-natural-700 tracking-wide">Session Log</h1>
            <p className="text-natural-500 text-sm mt-1 font-mono">{sessionId}</p>
          </div>
          <button
            onClick={() => navigate('/prep-sessions')}
            className="px-4 py-2 bg-sage-400 text-white rounded-xl hover:bg-sage-500 shadow-natural font-medium tracking-wide text-sm"
          >
            Back to Sessions
          </button>
        </div>

        {/* Session summary */}
        <div className="bg-white rounded-xl border border-cream-300 shadow-natural p-4 mb-6 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-natural-500">Status</span>
            <p className="font-medium text-natural-700 mt-0.5">{log?.status}</p>
          </div>
          <div>
            <span className="text-natural-500">Started</span>
            <p className="font-medium text-natural-700 mt-0.5">{formatDate(log?.startedAt ?? null)}</p>
          </div>
          <div>
            <span className="text-natural-500">Ended</span>
            <p className="font-medium text-natural-700 mt-0.5">{formatDate(log?.endedAt ?? null)}</p>
          </div>
          <div>
            <span className="text-natural-500">Events</span>
            <p className="font-medium text-natural-700 mt-0.5">{log?.events.length ?? 0}</p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex gap-2 mb-4">
          {['all', 'utterance', 'card_update', 'ai_usage', 'session'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filter === f
                  ? 'bg-sage-400 text-white'
                  : 'bg-cream-50 border border-cream-300 text-natural-600 hover:bg-white'
              }`}
            >
              {f === 'all' ? 'All' : f === 'utterance' ? 'Transcript' : f === 'card_update' ? 'Cards' : f === 'ai_usage' ? 'AI Usage' : 'Session'}
            </button>
          ))}
        </div>

        {/* Timeline */}
        <div className="bg-white rounded-xl border border-cream-300 shadow-natural overflow-hidden">
          {filteredEvents.length === 0 ? (
            <div className="px-6 py-12 text-center text-natural-500">No events found</div>
          ) : (
            <div className="divide-y divide-cream-200">
              {filteredEvents.map((event, idx) => (
                <div key={idx} className="px-5 py-3 flex gap-4 items-start hover:bg-cream-50">
                  <span className="text-xs text-natural-400 font-mono whitespace-nowrap pt-0.5 min-w-[70px]">
                    {formatTime(event.timestamp)}
                  </span>
                  <EventBadge type={event.type} />
                  <div className="flex-1 min-w-0">
                    <EventContent event={event} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function EventBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    session: 'bg-cream-200 text-natural-700',
    utterance: 'bg-sage-100 text-sage-700',
    card_update: 'bg-wood-100 text-wood-600',
    ai_usage: 'bg-cream-300 text-natural-600',
  }
  const labels: Record<string, string> = {
    session: 'Session',
    utterance: 'Speech',
    card_update: 'Card',
    ai_usage: 'AI',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide ${styles[type] || ''}`}>
      {labels[type] || type}
    </span>
  )
}

function EventContent({ event }: { event: LogEvent }) {
  switch (event.type) {
    case 'session':
      return <p className="text-sm text-natural-700 font-medium">Session {event.action}</p>
    case 'utterance':
      return (
        <p className="text-sm text-natural-700">{event.transcript}</p>
      )
    case 'card_update':
      return (
        <div>
          <p className="text-sm text-natural-700">
            Card <span className="font-mono text-xs">{event.cardId?.slice(0, 8)}</span> →{' '}
            <span className="font-medium">{event.status}</span>
            {event.confidence != null && (
              <span className="text-natural-500 ml-2">({Math.round(event.confidence * 100)}%)</span>
            )}
          </p>
          {event.evidenceTranscript && (
            <p className="text-xs text-natural-500 mt-0.5 line-clamp-2">{event.evidenceTranscript}</p>
          )}
        </div>
      )
    case 'ai_usage':
      return (
        <p className="text-sm text-natural-700">
          <span className="font-medium">{event.operation}</span>
          <span className="text-natural-500 ml-2">{event.model}</span>
          <span className="text-natural-500 ml-2">{event.totalTokens?.toLocaleString()} tokens</span>
          <span className="text-natural-400 ml-2">${event.costUsd?.toFixed(4)}</span>
        </p>
      )
    default:
      return null
  }
}
