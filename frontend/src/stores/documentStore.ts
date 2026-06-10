/**
 * Document Store for InsightGuide
 */

import { create } from 'zustand'
import type { Document } from '@/types/document'

interface DocumentState {
  currentDocument: Document | null
  error: string | null
  setCurrentDocument: (document: Document | null) => void
  setError: (error: string | null) => void
  clearDocument: () => void
}

export const useDocumentStore = create<DocumentState>((set) => ({
  currentDocument: null,
  error: null,
  setCurrentDocument: (document) => set({ currentDocument: document }),
  setError: (error) => set({ error }),
  clearDocument: () => set({ currentDocument: null, error: null }),
}))
