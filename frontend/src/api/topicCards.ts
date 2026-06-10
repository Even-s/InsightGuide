/**
 * @deprecated Use questionCards.ts (questionCardsAPI) directly.
 * This module adapts the old TopicCard API interface to the unified QuestionCard API.
 */

import { questionCardsAPI, type QuestionCardFormData } from './questionCards'
import type { QuestionCard } from '@/types/questionCard'
import type { CardImportance, CoverageRule } from '@/types/questionCard'
export type { CardImportance, CoverageRule }

export type TopicType = QuestionCard['questionType']

export interface TopicCardFormData {
  slideId: string
  title: string
  suggestedScript: string
  importance: CardImportance
  description?: string
  topicType?: TopicType
  semanticAnchors?: string
  expectedKeywords?: string
  mustMentionFacts?: string
  coverageRule?: CoverageRule
  shortPrompt?: string
  estimatedSeconds?: number
}

export function cardToForm(card: QuestionCard): TopicCardFormData {
  return {
    slideId: card.sectionId,
    title: card.questionText,
    suggestedScript: card.suggestedFollowup ?? '',
    importance: card.importance,
    description: card.questionText,
    topicType: card.questionType,
    coverageRule: card.coverageRule,
    estimatedSeconds: card.estimatedSeconds,
  }
}

function toQuestionCardForm(form: TopicCardFormData): QuestionCardFormData {
  return {
    sectionId: form.slideId,
    questionText: form.title,
    suggestedFollowup: form.suggestedScript,
    importance: form.importance,
    questionType: form.topicType,
    estimatedSeconds: form.estimatedSeconds,
    coverageRule: form.coverageRule,
  }
}

export const topicCardsAPI = {
  async getDeckCards(deckId: string): Promise<QuestionCard[]> {
    return questionCardsAPI.getDocumentCards(deckId)
  },

  async getCard(cardId: string): Promise<QuestionCard> {
    return questionCardsAPI.getCard(cardId)
  },

  async createCard(form: TopicCardFormData): Promise<QuestionCard> {
    return questionCardsAPI.createCard(toQuestionCardForm(form))
  },

  async updateCard(cardId: string, form: TopicCardFormData): Promise<QuestionCard> {
    return questionCardsAPI.updateCard(cardId, toQuestionCardForm(form))
  },

  async deleteCard(cardId: string): Promise<void> {
    return questionCardsAPI.deleteCard(cardId)
  },

  async regenerateScript(cardId: string): Promise<QuestionCard> {
    return questionCardsAPI.regenerateFollowup(cardId)
  },

  async reorderSlideCards(slideId: string, cardIds: string[]): Promise<QuestionCard[]> {
    return questionCardsAPI.reorderSectionCards(slideId, cardIds)
  },
}
