import { useEffect, useRef } from 'react'

export interface CardCreatedEvent {
  type: 'CARD_CREATED'
  card_id: string
  slide_id: string
  slide_number: number
  card_index: number
  cards_in_slide: number
  progress: {
    current_card: number
    current_slide: number
    total_slides: number
    percentage: number
  }
}

export interface AnalysisCompleteEvent {
  type: 'ANALYSIS_COMPLETE'
  deck_id: string
  total_slides: number
  total_cards: number
  status: string
}

interface UseDeckEventsOptions {
  onCardCreated?: (data: CardCreatedEvent) => void
  onAnalysisComplete?: (data: AnalysisCompleteEvent) => void
  onError?: (error: Error) => void
}

export function useDeckEvents(deckId: string | undefined, options: UseDeckEventsOptions = {}) {
  const eventSourceRef = useRef<EventSource | null>(null)
  const optionsRef = useRef(options)

  useEffect(() => {
    optionsRef.current = options
  }, [options])

  useEffect(() => {
    if (!deckId) return

    const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8002'
    const eventSource = new EventSource(`${apiBaseUrl}/api/events/sessions/${deckId}/stream`)

    eventSourceRef.current = eventSource

    eventSource.addEventListener('connected', (e) => {
      console.log('🔌 Deck SSE connected:', e.data)
    })

    eventSource.addEventListener('CARD_CREATED', (e) => {
      try {
        const data: CardCreatedEvent = JSON.parse(e.data)
        console.log('🎴 Card created:', {
          card_id: data.card_id,
          slide: data.slide_number,
          progress: `${data.progress.current_card} cards, ${data.progress.percentage}%`
        })
        optionsRef.current.onCardCreated?.(data)
      } catch (err) {
        console.error('Failed to parse CARD_CREATED event:', err)
      }
    })

    eventSource.addEventListener('ANALYSIS_COMPLETE', (e) => {
      try {
        const data: AnalysisCompleteEvent = JSON.parse(e.data)
        console.log('✅ Analysis complete:', {
          total_slides: data.total_slides,
          total_cards: data.total_cards
        })
        optionsRef.current.onAnalysisComplete?.(data)
      } catch (err) {
        console.error('Failed to parse ANALYSIS_COMPLETE event:', err)
      }
    })

    eventSource.onerror = (error) => {
      console.error('❌ Deck SSE error:', error)
      if (eventSource.readyState === EventSource.CLOSED) {
        console.log('Deck SSE connection closed')
      }
      optionsRef.current.onError?.(new Error('SSE connection error'))
    }

    return () => {
      console.log('🔌 Closing deck SSE connection')
      eventSource.close()
    }
  }, [deckId])

  return {
    isConnected: eventSourceRef.current?.readyState === EventSource.OPEN
  }
}
