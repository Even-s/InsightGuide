import { apiClient } from './client';

export interface AIUsageSummary {
  inputTokens: number;
  cachedInputTokens: number;
  outputTokens: number;
  totalTokens: number;
  realtimeSeconds: number;
  totalCostUsd: number;
}

export interface PrepSessionResponse {
  id: string;
  documentId: string;
  documentTitle: string;
  userId: string;
  title?: string;
  status: 'preparing' | 'ready' | 'archived';
  createdAt: string;
  updatedAt: string;
  interviewSessionsCount: number;
  documentCostUsd: number;
  documentAiUsage: AIUsageSummary;
}

export interface PrepSessionListResponse {
  prepSessions: PrepSessionResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface PrepSessionListParams {
  status?: string;
  documentId?: string;
  limit?: number;
  offset?: number;
  sortBy?: 'createdAt' | 'updatedAt' | 'status';
  order?: 'asc' | 'desc';
}

export interface PrepSessionCreate {
  documentId: string;
  title?: string;
}

export interface PrepSessionUpdate {
  title?: string;
  status?: 'preparing' | 'ready' | 'archived';
}

export interface InterviewSessionForPrep {
  id: string;
  prepSessionId: string;
  documentId: string;
  userId: string;
  status: 'idle' | 'preparing' | 'ready' | 'interviewing' | 'paused' | 'recovering' | 'ended' | 'failed';
  currentThemeId?: string;
  startedAt?: string;
  endedAt?: string;
  createdAt: string;
  costUsd: number;
  aiUsage: AIUsageSummary;
}

const emptyUsage: AIUsageSummary = {
  inputTokens: 0,
  cachedInputTokens: 0,
  outputTokens: 0,
  totalTokens: 0,
  realtimeSeconds: 0,
  totalCostUsd: 0,
};

function normalizePrepSession(raw: Record<string, unknown>): PrepSessionResponse {
  return {
    id: raw.id as string,
    documentId: raw.documentId as string,
    documentTitle: raw.documentTitle as string,
    userId: raw.userId as string,
    title: raw.title as string | undefined,
    status: raw.status as PrepSessionResponse['status'],
    createdAt: raw.createdAt as string,
    updatedAt: raw.updatedAt as string,
    interviewSessionsCount: raw.interviewSessionsCount as number,
    documentCostUsd: raw.documentCostUsd as number,
    documentAiUsage: (raw.documentAiUsage ?? emptyUsage) as AIUsageSummary,
  };
}

export const prepSessionsAPI = {
  async listPrepSessions(params: PrepSessionListParams = {}): Promise<PrepSessionListResponse> {
    const response = await apiClient.get('/api/prep-sessions/', {
      params: {
        status: params.status,
        documentId: params.documentId,
        limit: params.limit || 50,
        offset: params.offset || 0,
        sortBy: params.sortBy || 'createdAt',
        order: params.order || 'desc',
      },
    });
    return {
      ...response.data,
      prepSessions: (response.data.prepSessions ?? []).map(normalizePrepSession),
    };
  },

  async createPrepSession(data: PrepSessionCreate): Promise<PrepSessionResponse> {
    const response = await apiClient.post('/api/prep-sessions/', {
      documentId: data.documentId,
      title: data.title,
    });
    return normalizePrepSession(response.data);
  },

  async getPrepSession(prepSessionId: string): Promise<PrepSessionResponse> {
    const response = await apiClient.get(`/api/prep-sessions/${prepSessionId}`);
    return normalizePrepSession(response.data);
  },

  async updatePrepSession(prepSessionId: string, data: PrepSessionUpdate): Promise<PrepSessionResponse> {
    const response = await apiClient.patch(`/api/prep-sessions/${prepSessionId}`, data);
    return normalizePrepSession(response.data);
  },

  async deletePrepSession(prepSessionId: string): Promise<void> {
    await apiClient.delete(`/api/prep-sessions/${prepSessionId}`);
  },

  async deleteAllPrepSessions(): Promise<void> {
    await apiClient.delete('/api/prep-sessions/all');
  },

  async getInterviewSessions(prepSessionId: string): Promise<InterviewSessionForPrep[]> {
    const response = await apiClient.get(`/api/prep-sessions/${prepSessionId}/interview-sessions`);
    return response.data;
  },

  async createInterviewSession(prepSessionId: string): Promise<InterviewSessionForPrep> {
    const response = await apiClient.post(`/api/prep-sessions/${prepSessionId}/interview-sessions`);
    return response.data;
  },

  async getPrepSessionStats() {
    const response = await apiClient.get('/api/prep-sessions/', {
      params: { limit: 1000, offset: 0 },
    });

    const prepSessions: PrepSessionResponse[] = (response.data.prepSessions ?? []).map(normalizePrepSession);
    const total = response.data.total;

    const preparing = prepSessions.filter((s) => s.status === 'preparing').length;
    const ready = prepSessions.filter((s) => s.status === 'ready').length;
    const archived = prepSessions.filter((s) => s.status === 'archived').length;

    const totalInterviewSessions = prepSessions.reduce(
      (sum, ps) => sum + ps.interviewSessionsCount,
      0
    );

    return {
      total,
      preparing,
      ready,
      archived,
      totalInterviewSessions,
    };
  },
};
