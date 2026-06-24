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
  evaluationSeq?: number;
}

interface SSEEvidenceEvent {
  type: 'CARD_EVIDENCE_ADDED';
  card_id: string;
  criterion_id: string;
  status: string;
  evidence_quote: string | null;
  completion_score: number;
  evaluationSeq: number;
}

interface CandidateCard {
  cardId: string;
  questionText: string;
  focusText: string;
  score: number;
  status: string;
}

interface QuestionCandidatesEvent {
  utterance_id: string;
  candidates: CandidateCard[];
}

interface ActiveCardChangedEvent {
  card_id: string;
  status: string;
  source: string;
}

interface UseSSEEventsOptions {
  onCardListening?: (data: SSEEvent) => void;
  onCardCovered?: (data: SSEEvent) => void;
  onCardProbablyCovered?: (data: SSEEvent) => void;
  onCardAtRisk?: (data: SSEEvent) => void;
  onCardSkipped?: (data: SSEEvent) => void;
  onCardEvidenceAdded?: (data: SSEEvidenceEvent) => void;
  onQuestionCardCandidates?: (data: QuestionCandidatesEvent) => void;
  onActiveCardChanged?: (data: ActiveCardChangedEvent) => void;
  onCardManuallyCompleted?: (data: SSEEvent) => void;
  onActiveCardCleared?: () => void;
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

    eventSource.addEventListener('CARD_TOPIC_DETECTED', (e) => {
      const data: SSEEvent = JSON.parse(e.data);
      console.log('💡 CARD_TOPIC_DETECTED:', { card_id: data.card_id });
      optionsRef.current.onCardListening?.(data);
    });

    eventSource.addEventListener('CARD_PROGRESS_CHANGED', (e) => {
      const data: SSEEvent = JSON.parse(e.data);
      console.log('📊 CARD_PROGRESS_CHANGED:', { card_id: data.card_id, completion: data.confidence });
      optionsRef.current.onCardProbablyCovered?.(data);
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

    eventSource.addEventListener('CARD_EVIDENCE_ADDED', (e) => {
      const data: SSEEvidenceEvent = JSON.parse(e.data);
      optionsRef.current.onCardEvidenceAdded?.(data);
    });

    eventSource.addEventListener('QUESTION_CARD_CANDIDATES', (e) => {
      const data: QuestionCandidatesEvent = JSON.parse(e.data);
      console.log('🎯 QUESTION_CARD_CANDIDATES:', data.candidates.length, 'candidates');
      optionsRef.current.onQuestionCardCandidates?.(data);
    });

    eventSource.addEventListener('ACTIVE_CARD_CHANGED', (e) => {
      const data: ActiveCardChangedEvent = JSON.parse(e.data);
      console.log('🎯 ACTIVE_CARD_CHANGED:', data.card_id);
      optionsRef.current.onActiveCardChanged?.(data);
    });

    eventSource.addEventListener('CARD_MANUALLY_COMPLETED', (e) => {
      const data: SSEEvent = JSON.parse(e.data);
      console.log('✅ CARD_MANUALLY_COMPLETED:', data.card_id);
      optionsRef.current.onCardManuallyCompleted?.(data);
    });

    eventSource.addEventListener('ACTIVE_CARD_CLEARED', () => {
      console.log('🎯 ACTIVE_CARD_CLEARED');
      optionsRef.current.onActiveCardCleared?.();
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
