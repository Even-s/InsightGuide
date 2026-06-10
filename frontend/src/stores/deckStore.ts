/**
 * Deck state management with Zustand
 */

import { create } from 'zustand'
import { Deck } from '@/api/decks'

interface DeckState {
  currentDeck: Deck | null
  isLoading: boolean
  error: string | null
  setCurrentDeck: (deck: Deck | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useDeckStore = create<DeckState>((set) => ({
  currentDeck: null,
  isLoading: false,
  error: null,
  setCurrentDeck: (deck) => set({ currentDeck: deck }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}))
