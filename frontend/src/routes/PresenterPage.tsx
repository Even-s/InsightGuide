import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { presentationAPI } from '@/api/presentation'
import { prepSessionsAPI } from '@/api/prepSessions'
import { apiClient } from '@/api/client'
import PresenterLayout from '@/components/PresenterMode/PresenterLayout'
import Button from '@/components/common/Button'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import type { PresentationSession } from '@/types/presentation'

export default function PresenterPage() {
  const { deckId } = useParams<{ deckId: string }>()
  const [searchParams] = useSearchParams()
  const [projectId, setProjectId] = useState(searchParams.get('projectId') || undefined)
  const [stakeholderId, setStakeholderId] = useState(searchParams.get('stakeholderId') || undefined)
  const [session, setSession] = useState<PresentationSession | null>(null)
  const [isCreating, setIsCreating] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!deckId) {
      setError('Missing deck id')
      setIsCreating(false)
      return
    }

    let isMounted = true

    async function createSession() {
      try {
        setIsCreating(true)
        setError(null)

        // Auto-detect project/stakeholder from document if not provided via URL
        let resolvedProjectId = projectId
        let resolvedStakeholderId = stakeholderId
        if (!resolvedProjectId) {
          try {
            const docRes = await apiClient.get(`/api/documents/${deckId!}`)
            const doc = docRes.data
            if (doc.projectId || doc.project_id) {
              resolvedProjectId = doc.projectId || doc.project_id
              setProjectId(resolvedProjectId)

              // Try to find the stakeholder linked to this document
              const stakeholders = await apiClient.get(`/api/projects/${resolvedProjectId}/stakeholders`)
              for (const s of stakeholders.data) {
                try {
                  const guide = await apiClient.get(`/api/projects/${resolvedProjectId}/stakeholders/${s.id}/interview-guide`)
                  if (guide.data.document_id === deckId) {
                    resolvedStakeholderId = s.id
                    setStakeholderId(resolvedStakeholderId)
                    break
                  }
                } catch { /* no guide for this stakeholder */ }
              }
            }
          } catch { /* document lookup failed, proceed without context */ }
        }

        // Find or create a prep session for this deck
        const prepSessionsResponse = await prepSessionsAPI.listPrepSessions({
          deckId: deckId!,
          status: 'ready',
          limit: 1
        })

        let prepSessionId: string

        if (prepSessionsResponse.prepSessions.length > 0) {
          prepSessionId = prepSessionsResponse.prepSessions[0].id
        } else {
          const newPrepSession = await prepSessionsAPI.createPrepSession({
            deckId: deckId!,
            title: 'Quick Start Session'
          })
          await prepSessionsAPI.updatePrepSession(newPrepSession.id, { status: 'ready' })
          prepSessionId = newPrepSession.id
        }

        // Create the interview session with project context
        const created = await presentationAPI.createSession(deckId!, prepSessionId, {
          projectId: resolvedProjectId,
          stakeholderProfileId: resolvedStakeholderId,
        })
        if (isMounted) setSession(created)
      } catch (err: unknown) {
        if (isMounted) {
          setError(getErrorMessage(err))
        }
      } finally {
        if (isMounted) setIsCreating(false)
      }
    }

    createSession()

    return () => {
      isMounted = false
    }
  }, [deckId])

  if (!deckId) {
    return <ErrorState message="Missing deck id" />
  }

  if (isCreating) {
    return (
      <div className="h-screen bg-cream-100">
        <LoadingSpinner label="建立演講 Session..." />
      </div>
    )
  }

  if (error || !session) {
    return <ErrorState message={error || 'No session created'} />
  }

  return <PresenterLayout sessionId={session.id} deckId={deckId} />
}

function getErrorMessage(error: unknown) {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response
    if (typeof response?.data?.detail === 'string') return response.data.detail
  }

  return error instanceof Error ? error.message : 'Failed to create presentation session'
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex h-screen items-center justify-center bg-cream-100 p-6">
      <div className="max-w-md rounded border border-red-200 bg-white p-6 text-center">
        <p className="mb-2 text-lg font-semibold text-red-700">無法進入演講模式</p>
        <p className="mb-5 text-sm text-natural-500">{message}</p>
        <div className="flex justify-center">
          <Button onClick={() => window.location.reload()}>重試</Button>
        </div>
      </div>
    </div>
  )
}
