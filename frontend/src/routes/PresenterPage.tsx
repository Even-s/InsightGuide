import { useEffect, useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { presentationAPI } from '@/api/presentation'
import { prepSessionsAPI } from '@/api/prepSessions'
import { apiClient } from '@/api/client'
import PresenterLayout from '@/components/PresenterMode/PresenterLayout'
import Button from '@/components/common/Button'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import type { PresentationSession } from '@/types/presentation'

export default function PresenterPage() {
  const { deckId, sessionId: urlSessionId } = useParams<{ deckId?: string; sessionId?: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [session, setSession] = useState<PresentationSession | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Mode 1: Direct session access via /interview/session/:sessionId
    if (urlSessionId) {
      loadExistingSession(urlSessionId)
      return
    }

    // Mode 2: Create/find session via /interview/:deckId
    if (deckId) {
      findOrCreateSession()
      return
    }

    setError('Missing session or deck id')
    setIsLoading(false)
  }, [deckId, urlSessionId])

  async function loadExistingSession(sessionId: string) {
    try {
      setIsLoading(true)
      const sessionData = await presentationAPI.getSession(sessionId)
      setSession(sessionData)
    } catch (err: unknown) {
      setError(getErrorMessage(err))
    } finally {
      setIsLoading(false)
    }
  }

  async function findOrCreateSession() {
    try {
      setIsLoading(true)
      setError(null)

      const projectId = searchParams.get('projectId') || undefined
      const stakeholderId = searchParams.get('stakeholderId') || undefined

      // Auto-detect project/stakeholder from document if not provided
      let resolvedProjectId = projectId
      let resolvedStakeholderId = stakeholderId

      if (!resolvedProjectId) {
        try {
          const docRes = await apiClient.get(`/api/documents/${deckId!}`)
          const doc = docRes.data
          resolvedProjectId = doc.projectId || doc.project_id
        } catch { /* document lookup failed */ }
      }

      if (resolvedProjectId && !resolvedStakeholderId) {
        try {
          const stakeholders = await apiClient.get(`/api/projects/${resolvedProjectId}/stakeholders`)
          for (const s of stakeholders.data) {
            try {
              const guide = await apiClient.get(`/api/projects/${resolvedProjectId}/stakeholders/${s.id}/interview-guide`)
              if (guide.data.document_id === deckId) {
                resolvedStakeholderId = s.id
                break
              }
            } catch { /* no guide for this stakeholder */ }
          }
        } catch { /* stakeholder lookup failed */ }
      }

      // Check if an active (non-ended) session already exists for this deck
      try {
        const sessionsRes = await apiClient.get('/api/interview-sessions', {
          params: { projectId: resolvedProjectId, limit: 50 }
        })
        const sessions = sessionsRes.data?.sessions || sessionsRes.data || []
        const existing = sessions.find((s: PresentationSession) =>
          s.documentId === deckId &&
          s.status !== 'ended' &&
          (!resolvedStakeholderId || s.stakeholderProfileId === resolvedStakeholderId)
        )
        if (existing) {
          navigate(`/interview/session/${existing.id}`, { replace: true })
          return
        }
      } catch { /* list failed, proceed to create */ }

      // No existing session — create one
      const prepSessionsResponse = await prepSessionsAPI.listPrepSessions({
        deckId: deckId!,
        status: 'ready',
        limit: 1,
      })

      let prepSessionId: string
      if (prepSessionsResponse.prepSessions.length > 0) {
        prepSessionId = prepSessionsResponse.prepSessions[0].id
      } else {
        const newPrepSession = await prepSessionsAPI.createPrepSession({
          deckId: deckId!,
          title: 'Quick Start Session',
        })
        await prepSessionsAPI.updatePrepSession(newPrepSession.id, { status: 'ready' })
        prepSessionId = newPrepSession.id
      }

      const created = await presentationAPI.createSession(deckId!, prepSessionId, {
        projectId: resolvedProjectId,
        stakeholderProfileId: resolvedStakeholderId,
      })

      // Redirect to session-based URL so refresh won't re-create
      navigate(`/interview/session/${created.id}`, { replace: true })
    } catch (err: unknown) {
      setError(getErrorMessage(err))
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="h-screen bg-cream-100">
        <LoadingSpinner label="載入訪談 Session..." />
      </div>
    )
  }

  if (error || !session) {
    return <ErrorState message={error || 'No session found'} />
  }

  return <PresenterLayout sessionId={session.id} deckId={session.documentId} />
}

function getErrorMessage(error: unknown) {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response
    if (typeof response?.data?.detail === 'string') return response.data.detail
  }
  return error instanceof Error ? error.message : 'Failed to load interview session'
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex h-screen items-center justify-center bg-cream-100 p-6">
      <div className="max-w-md rounded border border-red-200 bg-white p-6 text-center">
        <p className="mb-2 text-lg font-semibold text-red-700">無法進入訪談模式</p>
        <p className="mb-5 text-sm text-natural-500">{message}</p>
        <div className="flex justify-center">
          <Button onClick={() => window.location.reload()}>重試</Button>
        </div>
      </div>
    </div>
  )
}
