/**
 * 簡體中文轉繁體中文工具
 */

import OpenCC from 'opencc-js'

// 初始化轉換器（簡體 → 繁體台灣）
const converter = OpenCC.Converter({ from: 'cn', to: 'tw' })

/**
 * 將簡體中文轉換為繁體中文（台灣正體）
 *
 * @param text - 可能包含簡體中文的文字
 * @returns 轉換為繁體中文的文字
 *
 * @example
 * ```typescript
 * simplifiedToTraditional('我们来看一下热门股票')
 * // 返回：'我們來看一下熱門股票'
 * ```
 */
export function simplifiedToTraditional(text: string): string {
  if (!text) return text

  try {
    return converter(text)
  } catch (error) {
    console.error('Error converting simplified to traditional Chinese:', error)
    return text // 轉換失敗時返回原文
  }
}
