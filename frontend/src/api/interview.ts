import { apiClient } from './client';
import type { CardState, InterviewCardState, InterviewSession, DocumentSection } from '../types/interview';
import type { CardStatus, QuestionCard } from '../types/questionCard';

type ApiRecord = Record<string, unknown>;

function asString(value: unknown) {
  return typeof value === 'string' ? value : undefined;
}

function asNumber(value: unknown) {
  return typeof value === 'number' ? value : 0;
}

function normalizeImageUrl(value: unknown) {
  const url = asString(value);
  if (!url) return undefined;
  return url.replace('http://minio:9000', 'http://localhost:9000');
}

function normalizeSection(raw: ApiRecord): DocumentSection {
  return {
    id: asString(raw.id) ?? '',
    documentId: asString(raw.documentId) ?? asString(raw.document_id) ?? asString(raw.deckId) ?? asString(raw.deck_id) ?? '',
    pageNumber: asNumber(raw.pageNumber ?? raw.page_number),
    title: asString(raw.title),
    imageUrl: normalizeImageUrl(raw.imageUrl ?? raw.image_url),
    extractedText: asString(raw.extractedText) ?? asString(raw.extracted_text),
    speakerNotes: asString(raw.speakerNotes) ?? asString(raw.speaker_notes),
    aiSummary: asString(raw.aiSummary) ?? asString(raw.ai_summary),
    topicCardsCount: asNumber(raw.topicCardsCount ?? raw.topic_cards_count),
    createdAt: asString(raw.createdAt) ?? asString(raw.created_at),
  };
}

function normalizeCardState(raw: ApiRecord): InterviewCardState {
  return {
    id: asString(raw.id) ?? '',
    sessionId: asString(raw.sessionId) ?? '',
    topicCardId: asString(raw.questionCardId) ?? asString(raw.topicCardId) ?? '',
    status: raw.status as InterviewCardState['status'],
    confidence: typeof raw.confidence === 'number' ? raw.confidence : null,
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
    opts?: { projectId?: string; stakeholderProfileId?: string }
  ): Promise<InterviewSession> {
    const response = await apiClient.post('/api/interview-sessions/', {
      prepSessionId,
      documentId,
      ...(opts?.projectId && { projectId: opts.projectId }),
      ...(opts?.stakeholderProfileId && { stakeholderProfileId: opts.stakeholderProfileId }),
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

  async getSections(documentId: string): Promise<DocumentSection[]> {
    const response = await apiClient.get(`/api/documents/${documentId}/analysis`);
    const sections = Array.isArray(response.data.sections) ? response.data.sections :
                     Array.isArray(response.data.slides) ? response.data.slides : [];
    return sections.map((s: ApiRecord) => normalizeSection(s));
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

  async getSessionCards(sessionId: string, documentId: string): Promise<CardState[]> {
    const [cardStates, questionCards] = await Promise.all([
      this.getCardStates(sessionId),
      this.getDocumentQuestionCards(documentId),
    ]);

    const cardsById = new Map(questionCards.map((card) => [card.id, card]));

    const combined: CardState[] = [];

    for (const state of cardStates) {
      const questionCard = cardsById.get(state.topicCardId);
      if (!questionCard) continue;
      combined.push({
        ...state,
        questionCard: {
          ...questionCard,
          status: state.status,
          confidence: state.confidence ?? undefined,
        },
      });
    }

    return combined;
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
    themeId: string,
    realtimeItemId?: string,
    startedAt?: string,
    endedAt?: string,
    askedCardId?: string,
  ) {
    const response = await apiClient.post(
      `/api/interview-sessions/${sessionId}/utterances`,
      { transcript, themeId, sectionId: themeId, realtimeItemId, startedAt, endedAt, askedCardId }
    );
    return response.data;
  },

  async updateUtteranceSpeaker(sessionId: string, utteranceId: string, speaker: string) {
    const response = await apiClient.patch(
      `/api/interview-sessions/${sessionId}/utterances/${utteranceId}/speaker`,
      { speaker }
    );
    return response.data;
  },

  async matchPartialTranscript(
    sessionId: string,
    transcript: string,
    themeId: string,
    activeCardId: string,
    realtimeItemId?: string
  ): Promise<{ accepted: boolean; reason?: string }> {
    const response = await apiClient.post(
      `/api/interview-sessions/${sessionId}/partial-transcript-match`,
      { transcript, themeId, sectionId: themeId, activeCardId, realtimeItemId }
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

  async generateOutputs(sessionId: string): Promise<{
    brd: { markdown: string; openIssuesCount: number }
    transcript: { markdown: string; utteranceCount: number }
  }> {
    const response = await apiClient.post(`/api/interview-sessions/${sessionId}/outputs/generate`);
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

// Backward-compatible export
export const presentationAPI = interviewAPI;
