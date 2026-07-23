import { apiClient } from './client'

export interface DemoTemplate {
  id: string
  title: string
  description: string
  estimatedMinutes: number
  themeCount: number
  questionCount: number
}

export interface DemoSessionResult {
  templateId: string
  projectId: string
  stakeholderProfileId: string
  prepSessionId: string
  documentId: string
  sessionId: string
  expiresAt: string
  interviewPath: string
}

export async function listDemoTemplates(): Promise<DemoTemplate[]> {
  const response = await apiClient.get('/api/demo-sessions/templates')
  return response.data.templates
}

export async function createDemoSession(templateId: string): Promise<DemoSessionResult> {
  const response = await apiClient.post('/api/demo-sessions', { templateId })
  return response.data
}
