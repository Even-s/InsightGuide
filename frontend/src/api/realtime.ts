import { apiClient } from './client'

export interface RealtimeTranscriptionSession {
  token: string
  transcriptionModel: string
  expiresAt?: number
  sessionId?: string
}

export const realtimeAPI = {
  async createTranscriptionSession(): Promise<RealtimeTranscriptionSession> {
    const response = await apiClient.post('/api/realtime/transcription-session')
    return response.data
  },
}
