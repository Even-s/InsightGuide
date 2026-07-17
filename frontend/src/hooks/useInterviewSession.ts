import { useState, useEffect, useCallback, useRef } from 'react';
import { interviewAPI } from '../api/interview';
import type { InterviewSession, SessionStatus } from '../types/interview';
import apiClient from '../api/client';

export interface InterviewTheme {
  id: string
  themeNumber: number
  title: string
  rationale: string
  brdMapping: string[]
  priority: number
  estimatedMinutes: number | null
  orderIndex: number
  isEnabled: boolean
  rubricReady?: boolean
  cards: Array<{
    id: string
    focusText: string
    questionText: string
    importance: string
    suggestedFollowup: string
    expectedAnswerElements: string[]
    brdMapping: string[]
  }>
}

function parseApiDate(value?: string | null) {
  if (!value) return null;
  const normalized = value.endsWith('Z') || value.includes('+') ? value : `${value}Z`;
  const time = new Date(normalized).getTime();
  return Number.isFinite(time) ? time : null;
}

function calculateActiveElapsedMs(session: InterviewSession) {
  const startedAt = parseApiDate(session.startedAt);
  if (!startedAt) return 0;
  const pausedDurationMs = Math.max(0, session.pausedDurationSeconds ?? 0) * 1000;
  const pausedAt = session.status === 'paused' ? parseApiDate(session.pausedAt) : null;
  const endedAt = session.status === 'ended' ? parseApiDate(session.endedAt) : null;
  const effectiveEnd = pausedAt ?? endedAt ?? Date.now();
  return Math.max(0, effectiveEnd - startedAt - pausedDurationMs);
}

export function useInterviewSession(sessionId: string) {
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [themes, setThemes] = useState<InterviewTheme[]>([]);
  const [currentThemeIndex, setCurrentThemeIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [themePreparing, setThemePreparing] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const preparedThemes = useRef<Set<string>>(new Set());

  const prepareTheme = useCallback(async (themeId: string) => {
    if (preparedThemes.current.has(themeId)) return;
    setThemePreparing(true);
    try {
      await apiClient.post(`/api/interview-sessions/${sessionId}/prepare-theme`, { themeId });
      preparedThemes.current.add(themeId);
    } catch (err) {
      console.warn('Failed to prepare theme rubrics:', err);
    } finally {
      setThemePreparing(false);
    }
  }, [sessionId]);

  const loadSession = useCallback(async () => {
    try {
      setIsLoading(true);
      const sessionData = await interviewAPI.getSession(sessionId);

      if (sessionData.startedAt && sessionData.status.match(/presenting|paused/)) {
        const elapsedHours = calculateActiveElapsedMs(sessionData) / (1000 * 60 * 60);
        if (elapsedHours > 2) {
          const shouldEnd = window.confirm(
            `此 Session 已運行 ${Math.floor(elapsedHours)} 小時。\n建議結束舊 Session 並重新開始。`
          );
          if (shouldEnd) {
            try {
              await interviewAPI.endSession(sessionId);
            } catch (err) {
              console.warn('Failed to end stale session before redirect:', err);
            }
            window.location.href = `/editor/${sessionData.documentId}`;
            return;
          }
        }
      }

      setSession(sessionData);

      // Load themes from interview plan
      let loadedThemes: InterviewTheme[] = [];
      const planResponse = await apiClient.get(`/api/documents/${sessionData.documentId}/interview-plan`);
      const plan = planResponse.data;
      loadedThemes = (plan.themes || []).filter((t: InterviewTheme) => t.isEnabled);
      setThemes(loadedThemes);

      // Mark already-ready themes
      for (const t of loadedThemes) {
        if (t.rubricReady) preparedThemes.current.add(t.id);
      }

      // Prepare first theme rubrics (blocking before UI becomes ready)
      if (loadedThemes.length > 0 && !preparedThemes.current.has(loadedThemes[0].id)) {
        setThemePreparing(true);
        try {
          await apiClient.post(`/api/interview-sessions/${sessionId}/prepare-theme`, { themeId: loadedThemes[0].id });
          preparedThemes.current.add(loadedThemes[0].id);
        } catch (err) {
          console.warn('Failed to prepare first theme:', err);
        }
        setThemePreparing(false);
      }

      setIsLoading(false);
    } catch (err) {
      setError(err as Error);
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => { loadSession(); }, [loadSession]);

  const currentTheme = themes[currentThemeIndex] ?? null;

  const startPresenting = useCallback(async () => {
    try {
      const payload: { status: SessionStatus; currentThemeId?: string } = { status: 'interviewing' }
      if (currentTheme?.id) payload.currentThemeId = currentTheme.id

      const updated = await interviewAPI.updateSession(sessionId, payload);
      setSession(updated);
    } catch (err) {
      console.error('Failed to start:', err);
    }
  }, [sessionId, currentTheme]);

  const pausePresenting = useCallback(async () => {
    try {
      const updated = await interviewAPI.updateSession(sessionId, { status: 'paused' });
      setSession(updated);
    } catch (err) {
      console.error('Failed to pause:', err);
    }
  }, [sessionId]);

  const nextTheme = useCallback(async () => {
    const maxIndex = themes.length - 1;
    if (currentThemeIndex < maxIndex) {
      const newIndex = currentThemeIndex + 1;
      setCurrentThemeIndex(newIndex);
      const nextId = themes[newIndex]?.id;

      // Ensure theme rubrics are ready before evaluation can start
      if (nextId && themes[newIndex] && !preparedThemes.current.has(nextId)) {
        await prepareTheme(nextId);
      }

      try {
        await interviewAPI.updateSession(sessionId, { currentThemeId: nextId });
      } catch (err) {
        console.warn('Failed to update current theme:', err);
      }
    }
  }, [sessionId, themes, currentThemeIndex, prepareTheme]);

  const previousTheme = useCallback(async () => {
    if (currentThemeIndex > 0) {
      const newIndex = currentThemeIndex - 1;
      setCurrentThemeIndex(newIndex);
      const prevId = themes[newIndex]?.id;

      // Ensure theme rubrics are ready
      if (prevId && themes[newIndex] && !preparedThemes.current.has(prevId)) {
        await prepareTheme(prevId);
      }

      try {
        await interviewAPI.updateSession(sessionId, { currentThemeId: prevId });
      } catch (err) {
        console.warn('Failed to update current theme:', err);
      }
    }
  }, [sessionId, themes, currentThemeIndex, prepareTheme]);

  const endSession = useCallback(async () => {
    try {
      await interviewAPI.endSession(sessionId);
      const updated = await interviewAPI.getSession(sessionId);
      setSession(updated);
    } catch (err) {
      console.error('Failed to end session:', err);
    }
  }, [sessionId]);

  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') nextTheme();
      if (e.key === 'ArrowLeft') previousTheme();
      if (e.key === ' ') {
        e.preventDefault();
        if (session?.status === 'interviewing') pausePresenting();
        else if (session?.status === 'paused') startPresenting();
      }
    };
    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [session, nextTheme, previousTheme, startPresenting, pausePresenting]);

  return {
    session,
    themes,
    currentTheme,
    currentThemeIndex,
    isLoading,
    themePreparing,
    error,
    startPresenting,
    pausePresenting,
    nextTheme,
    previousTheme,
    endSession,
    reload: loadSession
  };
}
