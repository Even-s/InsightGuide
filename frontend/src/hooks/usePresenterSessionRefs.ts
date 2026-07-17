import { useEffect, useRef } from 'react'
import type { CardState } from '@/types/interview'
import type { InterviewTheme } from './useInterviewSession'

export interface PresenterSessionRefs {
  cardStatesRef: React.MutableRefObject<CardState[]>
  currentThemeRef: React.MutableRefObject<InterviewTheme | null>
  isPresentingRef: React.MutableRefObject<boolean>
}

export function usePresenterSessionRefs(
  cardStates: CardState[],
  currentTheme: InterviewTheme | null,
  sessionStatus: string | undefined,
): PresenterSessionRefs {
  const cardStatesRef = useRef<CardState[]>([])
  const currentThemeRef = useRef<InterviewTheme | null>(null)
  const isPresentingRef = useRef(false)

  useEffect(() => {
    cardStatesRef.current = cardStates
  }, [cardStates])

  useEffect(() => {
    currentThemeRef.current = currentTheme
  }, [currentTheme])

  useEffect(() => {
    isPresentingRef.current = sessionStatus === 'interviewing'
  }, [sessionStatus])

  return { cardStatesRef, currentThemeRef, isPresentingRef }
}
