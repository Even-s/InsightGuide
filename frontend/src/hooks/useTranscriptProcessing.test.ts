import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { PresenterSessionRefs } from './usePresenterSessionRefs'
import { useTranscriptProcessing } from './useTranscriptProcessing'

const mockMatchPartialTranscript = vi.fn().mockResolvedValue(undefined)
const mockCreateUtterance = vi.fn().mockResolvedValue(undefined)

vi.mock('@/api/interview', () => ({
  interviewAPI: {
    matchPartialTranscript: (...args: unknown[]) => mockMatchPartialTranscript(...args),
    createUtterance: (...args: unknown[]) => mockCreateUtterance(...args),
  },
}))

vi.mock('@/hooks/useRealtimeTranscription', () => ({
  useRealtimeTranscription: () => ({
    status: 'idle',
    isRecording: false,
    isTranscribing: false,
    startTranscription: vi.fn(),
    stopTranscription: vi.fn(),
    error: null,
  }),
}))

vi.mock('@/hooks/useMediaRecorder', () => ({
  useMediaRecorder: () => ({
    start: vi.fn(),
    stop: vi.fn().mockResolvedValue(null),
  }),
}))

vi.mock('@/utils/chineseConverter', () => ({
  simplifiedToTraditional: (text: string) => text,
}))

vi.mock('@/components/PresenterMode/presenterUtils', () => ({
  findAskedCard: () => null,
  getActiveCardId: () => 'card-1',
}))

function createMockRefs(): PresenterSessionRefs {
  return {
    cardStatesRef: { current: [] },
    currentThemeRef: { current: { id: 'theme-1', themeNumber: 1, title: 'Test', cards: [] } },
    currentSectionRef: { current: null },
    isPresentingRef: { current: true },
  } as unknown as PresenterSessionRefs
}

describe('useTranscriptProcessing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('initializes with empty state', () => {
    const { result } = renderHook(() =>
      useTranscriptProcessing({
        sessionId: 'session-1',
        refs: createMockRefs(),
        candidateCards: [],
        onBufferedAnswer: vi.fn(),
      }),
    )

    expect(result.current.transcriptHistory).toEqual([])
    expect(result.current.pendingTranscript).toBe('')
    expect(result.current.transcriptionError).toBeNull()
    expect(result.current.isPreparingToPresent).toBe(false)
    expect(result.current.isDiarizing).toBe(false)
  })

  it('handleStartRequested sets isPreparingToPresent', async () => {
    const { result } = renderHook(() =>
      useTranscriptProcessing({
        sessionId: 'session-1',
        refs: createMockRefs(),
        candidateCards: [],
        onBufferedAnswer: vi.fn(),
      }),
    )

    await act(async () => {
      await result.current.handleStartRequested()
    })

    expect(result.current.isPreparingToPresent).toBe(true)
  })

  it('setTranscriptionError updates error state', () => {
    const { result } = renderHook(() =>
      useTranscriptProcessing({
        sessionId: 'session-1',
        refs: createMockRefs(),
        candidateCards: [],
        onBufferedAnswer: vi.fn(),
      }),
    )

    act(() => {
      result.current.setTranscriptionError('Mic not available')
    })

    expect(result.current.transcriptionError).toBe('Mic not available')
  })

  it('setIsDiarizing updates diarizing state', () => {
    const { result } = renderHook(() =>
      useTranscriptProcessing({
        sessionId: 'session-1',
        refs: createMockRefs(),
        candidateCards: [],
        onBufferedAnswer: vi.fn(),
      }),
    )

    act(() => {
      result.current.setIsDiarizing(true)
    })

    expect(result.current.isDiarizing).toBe(true)
  })

  it('realtimeStatus starts as idle', () => {
    const { result } = renderHook(() =>
      useTranscriptProcessing({
        sessionId: 'session-1',
        refs: createMockRefs(),
        candidateCards: [],
        onBufferedAnswer: vi.fn(),
      }),
    )

    expect(result.current.realtimeStatus).toBe('idle')
  })

  it('exposes recording refs', () => {
    const { result } = renderHook(() =>
      useTranscriptProcessing({
        sessionId: 'session-1',
        refs: createMockRefs(),
        candidateCards: [],
        onBufferedAnswer: vi.fn(),
      }),
    )

    expect(result.current.recordingStartedAtRef.current).toBeNull()
    expect(result.current.finalRecordingBlobRef.current).toBeNull()
  })
})
