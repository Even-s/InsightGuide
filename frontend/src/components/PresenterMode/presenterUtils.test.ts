import { describe, expect, it } from 'vitest'
import type { CardState } from '@/types/interview'
import { findAskedCard } from './presenterUtils'

function cardState(id: string, questionText: string): CardState {
  return {
    status: 'pending',
    questionCard: {
      id,
      interviewThemeId: 'theme-1',
      sectionId: '',
      questionText,
      focusText: questionText,
    },
  } as CardState
}

describe('findAskedCard', () => {
  it('matches the spoken registration question to its exact card', () => {
    const states = [
      cardState(
        'card-sources',
        '目前櫃台收到的線上預約和當日掛號，通常是從哪些管道進來的？',
      ),
      cardState(
        'card-checks',
        '收到一筆掛號後，櫃台通常會先查哪些資料，再做哪些確認？',
      ),
    ]

    expect(
      findAskedCard(
        '收到一筆掛號後，櫃台通常會先查哪些資料，再做哪些確認？',
        states,
        'theme-1',
      ),
    ).toBe('card-checks')
  })
})
