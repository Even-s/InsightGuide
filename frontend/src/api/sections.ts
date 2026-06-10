/**
 * Section API functions for InsightGuide
 */

import apiClient from './client'
import type { Section, SectionWithQuestionCards } from '@/types/section'

export const sectionsAPI = {
  getSection: async (sectionId: string): Promise<Section> => {
    const response = await apiClient.get(`/api/sections/${sectionId}`)
    return response.data
  },

  getSectionWithQuestionCards: async (sectionId: string): Promise<SectionWithQuestionCards> => {
    const response = await apiClient.get(`/api/sections/${sectionId}/question-cards`)
    return response.data
  },
}
