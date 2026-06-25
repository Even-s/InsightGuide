import { useEffect, useRef } from 'react'
import type { CardState, DocumentSection } from '@/types/interview'
import type { InterviewTheme } from './useInterviewSession'

export interface PresenterSessionRefs {
  cardStatesRef: React.MutableRefObject<CardState[]>
  currentThemeRef: React.MutableRefObject<InterviewTheme | null>
  currentSectionRef: React.MutableRefObject<DocumentSection | null>
  isPresentingRef: React.MutableRefObject<boolean>
}

export function usePresenterSessionRefs(
  cardStates: CardState[],
  currentTheme: InterviewTheme | null,
  currentSection: DocumentSection | null,
  sessionStatus: string | undefined,
): PresenterSessionRefs {
  const cardStatesRef = useRef<CardState[]>([])
  const currentThemeRef = useRef<InterviewTheme | null>(null)
  const currentSectionRef = useRef<DocumentSection | null>(null)
  const isPresentingRef = useRef(false)

  useEffect(() => {
    cardStatesRef.current = cardStates
  }, [cardStates])

  useEffect(() => {
    currentThemeRef.current = currentTheme
    currentSectionRef.current = currentSection
  }, [currentTheme, currentSection])

  useEffect(() => {
    isPresentingRef.current = sessionStatus === 'interviewing'
  }, [sessionStatus])

  return { cardStatesRef, currentThemeRef, currentSectionRef, isPresentingRef }
}
