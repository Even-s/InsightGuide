import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { presentationAPI } from '@/api/presentation'
import { prepSessionsAPI } from '@/api/prepSessions'
import PresenterLayout from '@/components/PresenterMode/PresenterLayout'
import Button from '@/components/common/Button'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import type { PresentationSession } from '@/types/presentation'

export default function PresenterPage() {
  const { deckId } = useParams<{ deckId: string }>()
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

        // First, find or create a prep session for this deck
        // Check if there's an existing ready prep session
        const prepSessionsResponse = await prepSessionsAPI.listPrepSessions({
          deckId: deckId!,
          status: 'ready',
          limit: 1
        })

        let prepSessionId: string

        if (prepSessionsResponse.prepSessions.length > 0) {
          // Use existing ready prep session
          prepSessionId = prepSessionsResponse.prepSessions[0].id
        } else {
          // Create new prep session and set it to ready
          const newPrepSession = await prepSessionsAPI.createPrepSession({
            deckId: deckId!,
            title: 'Quick Start Session'
          })
          // Update status to ready
          await prepSessionsAPI.updatePrepSession(newPrepSession.id, { status: 'ready' })
          prepSessionId = newPrepSession.id
        }

        // Now create the presentation session under the prep session
        const created = await presentationAPI.createSession(deckId!, prepSessionId)
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
      <div className="h-screen bg-gray-50">
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
    <div className="flex h-screen items-center justify-center bg-gray-50 p-6">
      <div className="max-w-md rounded border border-red-200 bg-white p-6 text-center">
        <p className="mb-2 text-lg font-semibold text-red-700">無法進入演講模式</p>
        <p className="mb-5 text-sm text-gray-600">{message}</p>
        <div className="flex justify-center">
          <Button onClick={() => window.location.reload()}>重試</Button>
        </div>
      </div>
    </div>
  )
}
