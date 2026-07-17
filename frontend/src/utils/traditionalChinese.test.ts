import { describe, expect, it } from 'vitest'
import { normalizeTraditionalChinese, toTraditionalChinese } from './traditionalChinese'

describe('traditionalChinese utilities', () => {
  it('converts simplified Chinese text to Taiwan Traditional Chinese', () => {
    expect(toTraditionalChinese('线上预约和当日挂号资料')).toBe('線上預約和當日掛號資料')
  })

  it('recursively converts strings in JSON-like values', () => {
    expect(
      normalizeTraditionalChinese({
        title: '线上预约挂号系统',
        goals: ['确认预约流程', '整理柜台痛点'],
      }),
    ).toEqual({
      title: '線上預約掛號系統',
      goals: ['確認預約流程', '整理櫃檯痛點'],
    })
  })
})
