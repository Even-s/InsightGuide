import { useState, useEffect, useCallback } from 'react';
import { presentationAPI } from '../api/presentation';
import type { PresentationSession, Slide } from '../types/presentation';

function parseApiDate(value?: string | null) {
  if (!value) return null;
  const normalized = value.endsWith('Z') || value.includes('+') ? value : `${value}Z`;
  const time = new Date(normalized).getTime();
  return Number.isFinite(time) ? time : null;
}

function calculateActiveElapsedMs(session: PresentationSession) {
  const startedAt = parseApiDate(session.startedAt);
  if (!startedAt) return 0;

  const pausedDurationMs = Math.max(0, session.pausedDurationSeconds ?? 0) * 1000;
  const pausedAt = session.status === 'paused' ? parseApiDate(session.pausedAt) : null;
  const endedAt = session.status === 'ended' ? parseApiDate(session.endedAt) : null;
  const effectiveEnd = pausedAt ?? endedAt ?? Date.now();

  return Math.max(0, effectiveEnd - startedAt - pausedDurationMs);
}

export function usePresentationSession(sessionId: string) {
  const [session, setSession] = useState<PresentationSession | null>(null);
  const [slides, setSlides] = useState<Slide[]>([]);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const loadSession = useCallback(async () => {
    try {
      setIsLoading(true);
      const sessionData = await presentationAPI.getSession(sessionId);

      // Check if session has been running for too long (> 1 hours)
      if (sessionData.startedAt && sessionData.status.match(/presenting|paused/)) {
        const elapsedHours = calculateActiveElapsedMs(sessionData) / (1000 * 60 * 60);

        if (elapsedHours > 1) {
          const shouldEnd = window.confirm(
            `此 Session 已運行 ${Math.floor(elapsedHours)} 小時。\n` +
            `建議結束舊 Session 並重新開始。\n\n` +
            `• 點擊「確定」= 結束並返回編輯頁面\n` +
            `• 點擊「取消」= 繼續使用（不建議）`
          );

          if (shouldEnd) {
            // End the session and go back to editor
            try {
              await presentationAPI.endSession(sessionId);
            } catch (err) {
              console.error('Failed to end session:', err);
            }
            // Redirect back to editor to create a fresh session
            window.location.href = `/editor/${sessionData.documentId}`;
            return;
          }
        }
      }

      setSession(sessionData);

      const slidesData: Slide[] = await presentationAPI.getSlides(sessionData.documentId);
      setSlides(slidesData);

      if (sessionData.currentSectionId) {
      const index = slidesData.findIndex((s) => s.id === sessionData.currentSectionId);
        setCurrentSlideIndex(index >= 0 ? index : 0);
      }

      setIsLoading(false);
    } catch (err) {
      setError(err as Error);
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  const startPresenting = useCallback(async () => {
    try {
      const updated = await presentationAPI.updateSession(sessionId, {
        status: 'presenting',
        currentSectionId: slides[currentSlideIndex]?.id
      });
      setSession(updated);
    } catch (err) {
      console.error('Failed to start presenting:', err);
    }
  }, [sessionId, slides, currentSlideIndex]);

  const pausePresenting = useCallback(async () => {
    try {
      const updated = await presentationAPI.updateSession(sessionId, {
        status: 'paused'
      });
      setSession(updated);
    } catch (err) {
      console.error('Failed to pause:', err);
    }
  }, [sessionId]);

  const nextSlide = useCallback(async () => {
    if (currentSlideIndex < slides.length - 1) {
      const newIndex = currentSlideIndex + 1;
      setCurrentSlideIndex(newIndex);

      try {
        await presentationAPI.updateSession(sessionId, {
          currentSectionId: slides[newIndex].id
        });
      } catch (err) {
        console.error('Failed to update slide:', err);
      }
    }
  }, [sessionId, slides, currentSlideIndex]);

  const previousSlide = useCallback(async () => {
    if (currentSlideIndex > 0) {
      const newIndex = currentSlideIndex - 1;
      setCurrentSlideIndex(newIndex);

      try {
        await presentationAPI.updateSession(sessionId, {
          currentSectionId: slides[newIndex].id
        });
      } catch (err) {
        console.error('Failed to update slide:', err);
      }
    }
  }, [sessionId, slides, currentSlideIndex]);

  const endSession = useCallback(async () => {
    try {
      await presentationAPI.endSession(sessionId);
      const updated = await presentationAPI.getSession(sessionId);
      setSession(updated);
    } catch (err) {
      console.error('Failed to end session:', err);
    }
  }, [sessionId]);

  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') nextSlide();
      if (e.key === 'ArrowLeft') previousSlide();
      if (e.key === ' ') {
        e.preventDefault();
        if (session?.status === 'presenting') {
          pausePresenting();
        } else if (session?.status === 'paused') {
          startPresenting();
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [session, nextSlide, previousSlide, startPresenting, pausePresenting]);

  return {
    session,
    slides,
    currentSlide: slides[currentSlideIndex] || null,
    currentSlideIndex,
    isLoading,
    error,
    startPresenting,
    pausePresenting,
    nextSlide,
    previousSlide,
    endSession,
    reload: loadSession
  };
}
