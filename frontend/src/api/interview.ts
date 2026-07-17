import { apiClient } from './client';
import type { CardState, InterviewCardState, InterviewSession } from '../types/interview';
import type { CardStatus, QuestionCard } from '../types/questionCard';

type ApiRecord = Record<string, unknown>;

function asString(value: unknown) {
  return typeof value === 'string' ? value : undefined;
}

function normalizeCardState(raw: ApiRecord): InterviewCardState {
  const stateId = asString(raw.stateId) ?? asString(raw.id) ?? '';
  return {
    id: stateId,
    stateId,
    sessionId: asString(raw.sessionId) ?? '',
    questionCardId: asString(raw.questionCardId) ?? '',
    status: raw.status as InterviewCardState['status'],
    confidence: typeof raw.confidence === 'number' ? raw.confidence : null,
    activationScore: typeof raw.activationScore === 'number' ? raw.activationScore : undefined,
    completionScore: typeof raw.completionScore === 'number' ? raw.completionScore : undefined,
    completionSource: asString(raw.completionSource) ?? null,
    manualNote: asString(raw.manualNote) ?? null,
    coveredAt: asString(raw.coveredAt) ?? asString(raw.answeredAt) ?? null,
    evidenceTranscript: asString(raw.evidenceTranscript) ?? null,
    evidence: raw.evidence && typeof raw.evidence === 'object' ? raw.evidence as Record<string, unknown> : null,
    createdAt: asString(raw.createdAt) ?? '',
    updatedAt: asString(raw.updatedAt) ?? '',
  };
}

export const interviewAPI = {
  async createSession(
    documentId: string,
    prepSessionId: string,
    opts?: { projectId?: string; stakeholderProfileId?: string; interviewRoundId?: string }
  ): Promise<InterviewSession> {
    const response = await apiClient.post('/api/interview-sessions/', {
      prepSessionId,
      documentId,
      ...(opts?.projectId && { projectId: opts.projectId }),
      ...(opts?.stakeholderProfileId && { stakeholderProfileId: opts.stakeholderProfileId }),
      ...(opts?.interviewRoundId && { interviewRoundId: opts.interviewRoundId }),
    });
    return response.data;
  },

  async getSession(sessionId: string): Promise<InterviewSession> {
    const response = await apiClient.get(`/api/interview-sessions/${sessionId}`);
    return response.data;
  },

  async updateSession(
    sessionId: string,
    data: Partial<InterviewSession>
  ): Promise<InterviewSession> {
    const response = await apiClient.patch(
      `/api/interview-sessions/${sessionId}`,
      data
    );
    return response.data;
  },

  async endSession(sessionId: string): Promise<InterviewSession> {
    const response = await apiClient.post(
      `/api/interview-sessions/${sessionId}/end`
    );
    return response.data;
  },

  async getDocumentQuestionCards(documentId: string): Promise<QuestionCard[]> {
    const response = await apiClient.get(`/api/question-cards/document/${documentId}`);
    return response.data;
  },

  async getCardStates(sessionId: string): Promise<InterviewCardState[]> {
    const response = await apiClient.get(
      `/api/interview-sessions/${sessionId}/card-states`
    );
    const states = Array.isArray(response.data) ? response.data : [];
    return states.map((state: ApiRecord) => normalizeCardState(state));
  },

  async getSessionCards(sessionId: string): Promise<CardState[]> {
    const response = await apiClient.get(`/api/interview-sessions/${sessionId}/cards`);
    const cards = Array.isArray(response.data) ? response.data : [];
    return cards.map((raw: ApiRecord) => {
      const state = normalizeCardState(raw);
      const questionCard = raw.questionCard as QuestionCard;
      return {
        ...state,
        questionCard: {
          ...questionCard,
          status: state.status,
          confidence: state.confidence ?? undefined,
        },
      };
    });
  },

  async updateCardState(
    sessionId: string,
    cardStateId: string,
    data: {
      status: CardStatus;
      confidence?: number | null;
      evidenceTranscript?: string | null;
      evidence?: Record<string, unknown> | null;
    }
  ): Promise<InterviewCardState> {
    const response = await apiClient.patch(
      `/api/interview-sessions/${sessionId}/card-states/${cardStateId}`,
      data
    );
    return normalizeCardState(response.data);
  },

  async createUtterance(
    sessionId: string,
    transcript: string,
    themeId?: string,
    realtimeItemId?: string,
    startedAt?: string,
    endedAt?: string,
    askedCardIds?: string[],
  ) {
    const response = await apiClient.post(
      `/api/interview-sessions/${sessionId}/utterances`,
      { transcript, themeId, realtimeItemId, startedAt, endedAt, askedCardIds }
    );
    return response.data;
  },

  async confirmActiveCard(sessionId: string, cardId: string, source: string = 'user_confirmed') {
    const response = await apiClient.post(
      `/api/interview-sessions/${sessionId}/active-card`,
      { cardId, source }
    );
    return response.data;
  },

  async clearActiveCard(sessionId: string) {
    const response = await apiClient.delete(`/api/interview-sessions/${sessionId}/active-card`);
    return response.data;
  },

  async manualCompleteCard(sessionId: string, cardId: string, note?: string) {
    const response = await apiClient.post(
      `/api/interview-sessions/${sessionId}/cards/${cardId}/manual-complete`,
      { note: note || '' }
    );
    return response.data;
  },

  async undoCompleteCard(sessionId: string, cardId: string) {
    const response = await apiClient.post(
      `/api/interview-sessions/${sessionId}/cards/${cardId}/undo-complete`
    );
    return response.data;
  },

  async listSessions(params: {
    projectId?: string;
    stakeholderProfileId?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<{ sessions: InterviewSession[]; total: number }> {
    const response = await apiClient.get('/api/interview-sessions/', { params });
    return {
      sessions: response.data.sessions ?? [],
      total: response.data.total ?? 0,
    };
  },

  async deleteSession(sessionId: string): Promise<void> {
    await apiClient.delete(`/api/interview-sessions/${sessionId}`);
  },

  async forceEndSession(sessionId: string): Promise<InterviewSession> {
    const response = await apiClient.patch(
      `/api/interview-sessions/${sessionId}`,
      { status: 'ended' }
    );
    return response.data;
  },
};
