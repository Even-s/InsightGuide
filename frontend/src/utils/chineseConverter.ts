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

/**
 * 檢測文字是否包含簡體中文
 *
 * @param text - 要檢測的文字
 * @returns 是否包含簡體中文
 */
export function hasSimplifiedChinese(text: string): boolean {
  if (!text) return false

  // 常見簡體字列表（部分）
  const simplifiedChars = /[国会来对开关华发经业长为历东亚办电视单门应报时机无头标书库级议乐过际张观边饭样营产团区页轮环认话试当数验进记据达态码导论构称际额写响测约详证备纪运满码题层适费续扩护降币额盘摆挂换击简导况述适补况压乱购挤拖轨抛播坏沧显摄饰维触启顾辑绩编纵缓辖编储泽质侧紧奖寿荣称览众缺险缩购]/

  return simplifiedChars.test(text)
}
