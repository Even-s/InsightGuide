import { apiClient } from './client';

export interface AIUsageSummary {
  inputTokens: number;
  cachedInputTokens: number;
  outputTokens: number;
  totalTokens: number;
  realtimeSeconds: number;
  totalCostUsd: number;
}

export interface SessionWithDeck {
  id: string;
  prepSessionId: string;
  deckId: string;
  deckTitle: string;
  userId: string;
  status: 'idle' | 'preparing' | 'ready' | 'presenting' | 'paused' | 'slide_transitioning' | 'recovering' | 'ended' | 'failed';
  currentSlideId?: string;
  startedAt?: string;
  endedAt?: string;
  createdAt: string;
  duration?: number;
  costUsd: number;
  aiUsage: AIUsageSummary;
}

export interface SessionListResponse {
  sessions: SessionWithDeck[];
  total: number;
  limit: number;
  offset: number;
}

export interface SessionListParams {
  status?: string;
  deckId?: string;
  limit?: number;
  offset?: number;
  sortBy?: 'createdAt' | 'startedAt' | 'endedAt' | 'status';
  order?: 'asc' | 'desc';
}

export const sessionsAPI = {
  async listSessions(params: SessionListParams = {}): Promise<SessionListResponse> {
    const response = await apiClient.get('/api/interview-sessions/', {
      params: {
        status: params.status,
        deckId: params.deckId,
        limit: params.limit || 50,
        offset: params.offset || 0,
        sortBy: params.sortBy || 'createdAt',
        order: params.order || 'desc',
      },
    });
    return response.data;
  },

  async deleteSession(sessionId: string): Promise<void> {
    await apiClient.delete(`/api/interview-sessions/${sessionId}`);
  },

  async getSessionStats() {
    // Fetch enough sessions to calculate accurate stats (up to 1000)
    const response = await apiClient.get('/api/interview-sessions/', {
      params: { limit: 1000, offset: 0 },
    });

    const sessions = response.data.sessions as SessionWithDeck[];
    const total = response.data.total; // Use total from API response

    const active = sessions.filter((s) =>
      ['idle', 'preparing', 'ready', 'presenting', 'paused'].includes(s.status)
    ).length;
    const ended = sessions.filter((s) => s.status === 'ended').length;

    const durations = sessions
      .filter((s) => s.duration !== undefined && s.duration !== null)
      .map((s) => s.duration as number);

    const avgDuration = durations.length > 0
      ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)
      : 0;

    return {
      total,
      active,
      ended,
      avgDuration,
    };
  },
};
