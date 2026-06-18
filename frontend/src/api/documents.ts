/**
 * Document API functions for InsightGuide
 */

import apiClient from './client'
import type { Document, DocumentAnalysis } from '@/types/document'

export interface AIUsageSummary {
  inputTokens: number
  cachedInputTokens: number
  outputTokens: number
  totalTokens: number
  realtimeSeconds: number
  totalCostUsd: number
}

export interface DocumentStatus {
  id: string
  status: string
  message?: string
  costUsd: number
  aiUsage: AIUsageSummary
}

export const documentsAPI = {
  uploadDocument: async (file: File, title?: string, projectId?: string): Promise<Document> => {
    const formData = new FormData()
    formData.append('file', file)
    if (title) {
      formData.append('title', title)
    }
    if (projectId) {
      formData.append('project_id', projectId)
    }

    const response = await apiClient.post('/api/documents/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  createFromTopic: async (topic: string, title?: string, projectId?: string): Promise<Document> => {
    const response = await apiClient.post('/api/documents/from-topic', { topic, title, project_id: projectId })
    return response.data
  },

  getDocument: async (documentId: string): Promise<Document> => {
    const response = await apiClient.get(`/api/documents/${documentId}`)
    return response.data
  },

  getDocumentStatus: async (documentId: string): Promise<DocumentStatus> => {
    const response = await apiClient.get(`/api/documents/${documentId}/status`)
    return response.data
  },

  getDocumentAnalysis: async (documentId: string): Promise<DocumentAnalysis> => {
    const response = await apiClient.get(`/api/documents/${documentId}/analysis`)
    return response.data
  },

  deleteDocument: async (documentId: string): Promise<void> => {
    await apiClient.delete(`/api/documents/${documentId}`)
  },
}
