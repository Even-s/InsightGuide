import { useEffect, useRef, useCallback } from 'react';

export interface PrepStatusChangedEvent {
  type: 'PREP_STATUS_CHANGED';
  prepSessionId: string;
  status: 'preparing' | 'ready' | 'archived';
  deckId: string;
  timestamp: string;
}

export interface AnalysisProgressEvent {
  type: 'ANALYSIS_PROGRESS';
  prepSessionId: string;
  currentSlide: number;
  totalSlides: number;
  percentage: number;
  timestamp: string;
}

export type PrepSessionEvent = PrepStatusChangedEvent | AnalysisProgressEvent;

export interface UsePrepSessionEventsOptions {
  onPrepStatusChanged?: (event: PrepStatusChangedEvent) => void;
  onAnalysisProgress?: (event: AnalysisProgressEvent) => void;
  onError?: (error: Error) => void;
}

/**
 * Hook to subscribe to real-time prep session events via SSE.
 *
 * @param prepSessionId - Prep session ID to subscribe to
 * @param options - Event handlers
 *
 * @example
 * ```tsx
 * usePrepSessionEvents(prepSessionId, {
 *   onPrepStatusChanged: (event) => {
 *     console.log('Status changed:', event.status);
 *     // Update UI
 *   }
 * });
 * ```
 */
export function usePrepSessionEvents(
  prepSessionId: string | undefined,
  options: UsePrepSessionEventsOptions
) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const optionsRef = useRef(options);

  // Update options ref when they change
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  // Setup SSE connection
  useEffect(() => {
    if (!prepSessionId) return;

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001';
    const url = `${apiUrl}/api/prep-sessions/${prepSessionId}/events`;

    console.log(`🔌 Connecting to prep session events: ${prepSessionId}`);

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    // Handle connection open
    eventSource.addEventListener('open', () => {
      console.log('✅ Prep session SSE connection opened');
    });

    // Handle connected event
    eventSource.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data);
      console.log('✅ Connected to prep session events:', data);
    });

    // Handle PREP_STATUS_CHANGED event
    eventSource.addEventListener('PREP_STATUS_CHANGED', (e) => {
      const event = JSON.parse(e.data) as PrepStatusChangedEvent;
      console.log('📥 Prep status changed:', event);
      optionsRef.current.onPrepStatusChanged?.(event);
    });

    // Handle ANALYSIS_PROGRESS event
    eventSource.addEventListener('ANALYSIS_PROGRESS', (e) => {
      const event = JSON.parse(e.data) as AnalysisProgressEvent;
      console.log('📥 Analysis progress:', event);
      optionsRef.current.onAnalysisProgress?.(event);
    });

    // Handle errors
    eventSource.addEventListener('error', (e) => {
      console.error('❌ Prep session SSE error:', e);
      if (eventSource.readyState === EventSource.CLOSED) {
        console.log('Connection closed');
      }
      optionsRef.current.onError?.(new Error('SSE connection error'));
    });

    // Cleanup on unmount
    return () => {
      console.log('🔌 Disconnecting from prep session events');
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [prepSessionId]);

  // Return method to manually close connection
  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  return { disconnect };
}
