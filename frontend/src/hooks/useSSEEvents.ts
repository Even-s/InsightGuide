import { useEffect, useRef } from 'react';

interface SSEEvent {
  type: string;
  card_id?: string;
  title?: string;
  old_status?: string;
  new_status?: string;
  status?: string;
  confidence?: number;
  evidence?: Record<string, unknown>;
  evidenceTranscript?: string;
}

interface UseSSEEventsOptions {
  onCardListening?: (data: SSEEvent) => void;
  onCardCovered?: (data: SSEEvent) => void;
  onCardProbablyCovered?: (data: SSEEvent) => void;
  onCardAtRisk?: (data: SSEEvent) => void;
  onCardSkipped?: (data: SSEEvent) => void;
  onMatchingError?: (data: { error: string; utterance_id: string; timestamp: string }) => void;
}

export function useSSEEvents(sessionId: string, options: UseSSEEventsOptions = {}) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const optionsRef = useRef(options);

  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  useEffect(() => {
    if (!sessionId) return;

    const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8002';
    const eventSource = new EventSource(
      `${apiBaseUrl}/api/events/sessions/${sessionId}/stream`
    );

    eventSourceRef.current = eventSource;

    eventSource.addEventListener('connected', (e) => {
      console.log('SSE connected:', e.data);
    });

    eventSource.addEventListener('CARD_LISTENING', (e) => {
      const data: SSEEvent = JSON.parse(e.data);
      console.log('🎤 CARD_LISTENING event received:', {
        card_id: data.card_id,
        title: data.title,
        confidence: data.confidence,
        old_status: data.old_status,
        new_status: data.new_status,
        evidence: data.evidence
      });
      optionsRef.current.onCardListening?.(data);
    });

    eventSource.addEventListener('CARD_COVERED', (e) => {
      const data: SSEEvent = JSON.parse(e.data);
      console.log('✅ CARD_COVERED event received:', data);
      optionsRef.current.onCardCovered?.(data);
    });

    eventSource.addEventListener('CARD_PROBABLY_COVERED', (e) => {
      const data: SSEEvent = JSON.parse(e.data);
      console.log('⚠️ CARD_PROBABLY_COVERED event received:', data);
      optionsRef.current.onCardProbablyCovered?.(data);
    });

    eventSource.addEventListener('CARD_AT_RISK', (e) => {
      const data: SSEEvent = JSON.parse(e.data);
      console.log('Card at risk:', data);
      optionsRef.current.onCardAtRisk?.(data);
    });

    eventSource.addEventListener('CARD_SKIPPED', (e) => {
      const data: SSEEvent = JSON.parse(e.data);
      console.log('Card skipped:', data);
      optionsRef.current.onCardSkipped?.(data);
    });

    eventSource.addEventListener('MATCHING_ERROR', (e) => {
      const data = JSON.parse(e.data);
      console.error('❌ Topic Matching Error:', data);
      optionsRef.current.onMatchingError?.(data);
    });

    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      if (eventSource.readyState === EventSource.CLOSED) {
        console.log('SSE connection closed');
      }
    };

    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [sessionId]);

  return {
    isConnected: eventSourceRef.current?.readyState === EventSource.OPEN
  };
}
