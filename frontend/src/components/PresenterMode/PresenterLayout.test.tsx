import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import PresenterLayout from './PresenterLayout'

const mockUseInterviewSession = vi.fn()

vi.mock('@/hooks/useInterviewSession', () => ({
  useInterviewSession: (...args: unknown[]) => mockUseInterviewSession(...args),
}))

vi.mock('@/hooks/useResponsiveLayout', () => ({
  useResponsiveLayout: () => ({
    layoutConfig: { transcriptArea: { height: 'h-32' } },
  }),
}))

vi.mock('@/hooks/usePresenterSessionRefs', () => ({
  usePresenterSessionRefs: () => ({
    cardStatesRef: { current: [] },
    currentThemeRef: { current: null },
    currentSectionRef: { current: null },
    isPresentingRef: { current: false },
  }),
}))

vi.mock('@/hooks/useCardEventHandlers', () => ({
  useCardEventHandlers: () => ({
    cardStates: [],
    candidateCards: [],
    activeCardId: null,
    detectedCardId: null,
    bufferedAnswerCount: 0,
    followupQueue: [],
    skippedCards: new Set(),
    currentFollowupCard: undefined,
    followupPrompt: null,
    followupQueueLength: 0,
    setActiveCardId: vi.fn(),
    setCandidateCards: vi.fn(),
    setBufferedAnswerCount: vi.fn(),
    handleSkipFollowup: vi.fn(),
    updateCardFromEvent: vi.fn(),
  }),
}))

vi.mock('@/hooks/useTranscriptProcessing', () => ({
  useTranscriptProcessing: () => ({
    transcriptHistory: [],
    pendingTranscript: '',
    transcriptionError: null,
    isPreparingToPresent: false,
    realtimeStatus: 'idle',
    isRecording: false,
    isTranscribing: false,
    realtimeError: null,
    audioDiagnostics: {
      active: false,
      profile: 'standard',
      trackSettings: null,
      frequencyLevels: null,
      connectionState: 'idle',
      codec: null,
      bytesSent: 0,
      speechStartedCount: 0,
      speechStoppedCount: 0,
      transcriptDeltaCount: 0,
      transcriptCompletedCount: 0,
      lastCompletedTranscript: '',
      events: [],
      analyserError: null,
    },
    setTranscriptionError: vi.fn(),
    setIsPreparingToPresent: vi.fn(),
    handleStartRequested: vi.fn(),
    startTranscription: vi.fn(),
    stopTranscription: vi.fn(),
    flushTranscriptSaves: vi.fn().mockResolvedValue(undefined),
    resetAudioDiagnostics: vi.fn(),
  }),
}))

vi.mock('@/api/interview', () => ({
  interviewAPI: { confirmActiveCard: vi.fn() },
}))

const defaultSessionReturn = {
  session: null,
  themes: [],
  currentTheme: null,
  currentThemeIndex: 0,
  currentSection: null,
  sections: [],
  isLoading: true,
  themePreparing: false,
  error: null,
  startPresenting: vi.fn(),
  pausePresenting: vi.fn(),
  nextTheme: vi.fn(),
  previousTheme: vi.fn(),
  endSession: vi.fn(),
}

describe('PresenterLayout', () => {
  beforeEach(() => {
    mockUseInterviewSession.mockReturnValue(defaultSessionReturn)
  })

  it('shows loading spinner while session is loading', () => {
    render(<PresenterLayout sessionId="s1" documentId="d1" />)
    expect(screen.getByText('載入演講 Session...')).toBeInTheDocument()
  })

  it('shows error state when session load fails', () => {
    mockUseInterviewSession.mockReturnValue({
      ...defaultSessionReturn,
      isLoading: false,
      error: new Error('Network error'),
    })

    render(<PresenterLayout sessionId="s1" documentId="d1" />)
    expect(screen.getByText('載入失敗')).toBeInTheDocument()
    expect(screen.getByText('Network error')).toBeInTheDocument()
  })

  it('shows theme preparing state', () => {
    mockUseInterviewSession.mockReturnValue({
      ...defaultSessionReturn,
      session: { id: 's1', status: 'preparing' },
      isLoading: false,
      themePreparing: true,
    })

    render(<PresenterLayout sessionId="s1" documentId="d1" />)
    expect(screen.getByText('準備訪談問題中...')).toBeInTheDocument()
  })
})
