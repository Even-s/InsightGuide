export function formatThemeTitle(text?: string | null) {
  const normalized = normalizeInterviewCopy(text)
  if (isGoalAndScopeText(normalized)) {
    return '確認需求訪談助手的目標與範圍'
  }
  return normalized
}

export function formatFocusText(text?: string | null) {
  const normalized = normalizeInterviewCopy(text)
  if (isGoalText(normalized)) return '確認需求訪談助手的業務目標'
  if (isScopeText(normalized)) return '界定第一階段支援範圍'
  return normalized
}

export function formatQuestionText(text?: string | null) {
  const normalized = normalizeInterviewCopy(text)
  if (isGoalQuestion(normalized)) {
    return '想先請你說明，這個需求訪談助手第一階段最想解決的是什麼問題？'
  }
  if (isScopeQuestion(normalized)) {
    return '這個助手第一階段主要支援哪些需求訪談情境？哪些情境先不納入？'
  }
  return normalized
}

export function formatFollowupText(text?: string | null) {
  const normalized = normalizeInterviewCopy(text)
  if (isScopeText(normalized) || normalized.includes('不支援') || normalized.includes('排除')) {
    return '可以再補充不支援或延後處理的需求類型嗎？'
  }
  if (isGoalText(normalized) || normalized.includes('MVP')) {
    return '如果只能先做 MVP，哪些目標是這一階段一定要達成的？'
  }
  return normalized
}

export function normalizeInterviewCopy(text?: string | null) {
  if (!text) return ''

  return text
    .replace(/\bagent\s*的\s*agent\b/gi, '需求訪談助手')
    .replace(/需求訪談助手\s*的\s*agent/gi, '需求訪談助手')
    .replace(/需求訪談助手\s*agent/gi, '需求訪談助手')
    .replace(/\bagent\b/gi, '助手')
    .replace(/這一個/g, '這個')
    .replace(/能否描述/g, '請說明')
    .replace(/主要目標是什麼/g, '主要目標')
    .replace(/主要針對哪些需求範圍進行支援/g, '主要支援哪些需求範圍')
    .replace(/\s+/g, ' ')
    .trim()
}

function isGoalAndScopeText(text: string) {
  return text.includes('需求訪談助手') && text.includes('目標') && text.includes('範圍')
}

function isGoalText(text: string) {
  return text.includes('需求訪談助手') && text.includes('目標')
}

function isScopeText(text: string) {
  return text.includes('需求訪談助手') && (text.includes('範圍') || text.includes('支援'))
}

function isGoalQuestion(text: string) {
  return isGoalText(text) && (
    text.includes('請說明') ||
    text.includes('描述') ||
    text.includes('想要達到') ||
    text.includes('解決')
  )
}

function isScopeQuestion(text: string) {
  return isScopeText(text) && (
    text.includes('哪些') ||
    text.includes('範圍') ||
    text.includes('支援') ||
    text.includes('不納入')
  )
}
