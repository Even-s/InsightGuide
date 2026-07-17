import * as OpenCC from 'opencc-js'

const converter = OpenCC.Converter({ from: 'cn', to: 'tw' })

export function toTraditionalChinese(value: string | null | undefined): string {
  const text = (value || '').trim()
  return text ? converter(text).trim() : ''
}

export function normalizeTraditionalChinese<T>(value: T): T {
  if (typeof value === 'string') {
    return toTraditionalChinese(value) as T
  }
  if (Array.isArray(value)) {
    return value.map(item => normalizeTraditionalChinese(item)) as T
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, normalizeTraditionalChinese(item)]),
    ) as T
  }
  return value
}
