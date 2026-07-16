import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { PresenterSessionRefs } from './usePresenterSessionRefs'
import { useTranscriptProcessing } from './useTranscriptProcessing'

const mockMatchPartialTranscript = vi.fn().mockResolvedValue(undefined)
const mockCreateUtterance = vi.fn().mockResolvedValue(undefined)
const mockFindAskedCards = vi.fn().mockReturnValue([])
let realtimeCallbacks: {
  onTranscriptDelta?: (delta: string, itemId?: string) => void
  onTranscriptCompleted?: (payload: {
    transcript: string
    itemId?: string
    startedAt?: string
    endedAt?: string
  }) => void
} = {}

vi.mock('@/api/interview', () => ({
  interviewAPI: {
    matchPartialTranscript: (...args: unknown[]) => mockMatchPartialTranscript(...args),
    createUtterance: (...args: unknown[]) => mockCreateUtterance(...args),
  },
}))

vi.mock('@/hooks/useRealtimeTranscription', () => ({
  useRealtimeTranscription: (callbacks: typeof realtimeCallbacks) => {
    realtimeCallbacks = callbacks
    return {
      status: 'idle',
      isRecording: false,
      isTranscribing: false,
      startTranscription: vi.fn(),
      stopTranscription: vi.fn(),
      error: null,
      diagnostics: {},
      resetDiagnostics: vi.fn(),
    }
  },
}))

vi.mock('@/utils/chineseConverter', () => ({
  simplifiedToTraditional: (text: string) => text,
}))

vi.mock('@/components/PresenterMode/presenterUtils', () => ({
  findAskedCards: (...args: unknown[]) => mockFindAskedCards(...args),
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
    realtimeCallbacks = {}
    mockFindAskedCards.mockReturnValue([])
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

  it('keeps a richer streaming question when the completed transcript is truncated', async () => {
    renderHook(() =>
      useTranscriptProcessing({
        sessionId: 'session-1',
        refs: createMockRefs(),
        candidateCards: [],
        onBufferedAnswer: vi.fn(),
      }),
    )

    const fullQuestion = '收到一筆掛號後，櫃台通常會先查哪些資料，再做哪些確認？'
    mockFindAskedCards.mockReturnValue(['card-2', 'card-3'])

    await act(async () => {
      realtimeCallbacks.onTranscriptDelta?.(fullQuestion, 'item-1')
      realtimeCallbacks.onTranscriptCompleted?.({
        transcript: '目前我們認為',
        itemId: 'item-1',
      })
    })

    expect(mockCreateUtterance).toHaveBeenCalledWith(
      'session-1',
      fullQuestion,
      'theme-1',
      'item-1',
      undefined,
      undefined,
      'card-2',
      ['card-2', 'card-3'],
    )
  })

  it('stores Realtime transcript even when no interview unit is active', async () => {
    const refs = createMockRefs()
    refs.currentThemeRef.current = null

    const { result } = renderHook(() =>
      useTranscriptProcessing({
        sessionId: 'session-1',
        refs,
        candidateCards: [],
        onBufferedAnswer: vi.fn(),
      }),
    )

    await act(async () => {
      realtimeCallbacks.onTranscriptCompleted?.({
        transcript: '這一段也必須保留在完整逐字稿。',
        itemId: 'item-without-theme',
      })
      await result.current.flushTranscriptSaves()
    })

    expect(mockCreateUtterance).toHaveBeenCalledWith(
      'session-1',
      '這一段也必須保留在完整逐字稿。',
      undefined,
      'item-without-theme',
      undefined,
      undefined,
      undefined,
      undefined,
    )
  })

  it('previews likely question cards from partial transcript without saving state', async () => {
    const onPreviewDetectedCards = vi.fn()
    mockFindAskedCards.mockReturnValue(['card-2', 'card-3'])

    renderHook(() =>
      useTranscriptProcessing({
        sessionId: 'session-1',
        refs: createMockRefs(),
        candidateCards: [],
        onBufferedAnswer: vi.fn(),
        onPreviewDetectedCards,
      }),
    )

    await act(async () => {
      realtimeCallbacks.onTranscriptDelta?.('收到一筆掛號後，櫃台通常會先查哪些資料', 'item-1')
    })

    expect(mockFindAskedCards).toHaveBeenCalledWith(
      '收到一筆掛號後，櫃台通常會先查哪些資料',
      [],
      'theme-1',
      2,
      {
        requireQuestionEnding: false,
        minScore: 1.4,
        includeListening: false,
      },
    )
    expect(onPreviewDetectedCards).toHaveBeenCalledWith(['card-2', 'card-3'])
  })
})
