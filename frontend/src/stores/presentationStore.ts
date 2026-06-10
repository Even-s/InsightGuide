/**
 * Presentation runtime state management with Zustand
 */

import { create } from 'zustand'
import { PresentationRuntimeState, SessionStatus } from '@/types/presentation'
import { QuestionCard } from '@/types/questionCard'

interface PresentationStore extends PresentationRuntimeState {
  updateStatus: (status: SessionStatus) => void
  updateCurrentSlide: (slideId: string, pageNumber: number) => void
  updateCardState: (slideId: string, cardId: string, updates: Partial<QuestionCard>) => void
  addUtterance: (utterance: PresentationRuntimeState['utterances'][number]) => void
  updateRealtimeConnection: (status: string) => void
  updateTranscriptDelta: (delta: string) => void
  reset: () => void
}

const initialState: PresentationRuntimeState = {
  sessionId: '',
  deckId: '',
  status: 'idle',
  currentSlideId: '',
  currentSlidePageNumber: 0,
  slideStartedAt: null,
  elapsedSecondsOnSlide: 0,
  estimatedSecondsOnSlide: 0,
  cardsBySlideId: {},
  realtime: {
    connectionStatus: 'disconnected',
    lastEventAt: null,
    lastTranscriptDelta: '',
  },
  utterances: [],
}

export const usePresentationStore = create<PresentationStore>((set) => ({
  ...initialState,

  updateStatus: (status) => set({ status }),

  updateCurrentSlide: (slideId, pageNumber) =>
    set({
      currentSlideId: slideId,
      currentSlidePageNumber: pageNumber,
      slideStartedAt: new Date().toISOString(),
      elapsedSecondsOnSlide: 0,
    }),

  updateCardState: (slideId, cardId, updates) =>
    set((state) => {
      const cards = state.cardsBySlideId[slideId] || []
      const updatedCards = cards.map((card) =>
        card.id === cardId ? { ...card, ...updates } : card
      )
      return {
        cardsBySlideId: {
          ...state.cardsBySlideId,
          [slideId]: updatedCards,
        },
      }
    }),

  addUtterance: (utterance) =>
    set((state) => ({
      utterances: [...state.utterances, utterance],
    })),

  updateRealtimeConnection: (status) =>
    set((state) => ({
      realtime: {
        ...state.realtime,
        connectionStatus: status as PresentationRuntimeState['realtime']['connectionStatus'],
        lastEventAt: new Date().toISOString(),
      },
    })),

  updateTranscriptDelta: (delta) =>
    set((state) => ({
      realtime: {
        ...state.realtime,
        lastTranscriptDelta: delta,
      },
    })),

  reset: () => set(initialState),
}))
