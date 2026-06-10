/**
 * Question Card TypeScript types for InsightGuide
 * Aligned with backend Pydantic schemas
 */

export type CardImportance = 'must' | 'should'

export type CardStatus =
  | 'pending'
  | 'listening'
  | 'probably_sufficient'
  | 'sufficient'
  | 'probably_covered'
  | 'covered'
  | 'at_risk'
  | 'skipped'
  | 'manually_checked'
  | 'disabled'

export type QuestionType =
  | 'clarification'
  | 'validation'
  | 'exploration'
  | 'edge_case'
  | 'constraint'
  | 'priority'

export interface MustMentionElement {
  text: string
  required: boolean
  aliases?: string[]
  subpoints?: string[]
}

export interface SufficiencyThresholds {
  probablySufficient: number
  sufficient: number
}

export interface ScoringWeights {
  semanticSimilarity: number
  keywordCoverage: number
  elementCoverage: number
}

export interface CoverageRule {
  semanticAnchors: string[]
  expectedKeywords: string[]
  mustMentionElements: MustMentionElement[]
  negativeSignals: string[]
  thresholds: SufficiencyThresholds
  scoringWeights: ScoringWeights
}

export interface SufficiencyEvidence {
  matchedUtteranceIds: string[]
  matchedTranscript?: string
  matchedAt?: string
  semanticScore?: number
  keywordScore?: number
  elementScore?: number
  finalScore?: number
  completionPercentage?: number
  gptConfidence?: number
  gptReasoning?: string
  coveredElementIds?: string[]
  missingElementIds?: string[]
}

export interface CardUI {
  color: 'default' | 'green' | 'yellow' | 'red' | 'gray'
  isVisible: boolean
  isPinned: boolean
  displayMode: 'full' | 'compact' | 'hidden'
}

export interface QuestionCard {
  id: string
  documentId: string
  sectionId: string
  sectionNumber: number
  questionText: string
  questionType: QuestionType
  importance: CardImportance
  coverageRule: CoverageRule
  suggestedFollowup?: string
  expectedAnswerElements: string[]
  estimatedSeconds?: number
  orderIndex: number
  status: CardStatus
  confidence?: number
  evidence?: SufficiencyEvidence
  ui?: CardUI
  createdBy: 'ai' | 'user' | 'system'
  createdAt: string
  updatedAt: string
  // Aliases returned by API for backward compatibility
  deckId?: string
  slideId?: string
  slidePageNumber?: number
  title?: string
  description?: string
  topicType?: QuestionType
  suggestedScript?: string
  shortPrompt?: string
}

/**
 * @deprecated Use QuestionCard directly. TopicCard is kept as an alias during migration.
 */
export type TopicCard = QuestionCard
