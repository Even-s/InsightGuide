import { apiClient } from './client';
import type { CardState, PresentationCardState, PresentationSession, Slide } from '../types/presentation';
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

function normalizeSlide(raw: ApiRecord): Slide {
  return {
    id: asString(raw.id) ?? '',
    deckId: asString(raw.deckId) ?? asString(raw.deck_id) ?? '',
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

function normalizeCardState(raw: ApiRecord): PresentationCardState {
  return {
    id: asString(raw.id) ?? '',
    sessionId: asString(raw.sessionId) ?? '',
    topicCardId: asString(raw.questionCardId) ?? asString(raw.topicCardId) ?? '',
    status: raw.status as PresentationCardState['status'],
    confidence: typeof raw.confidence === 'number' ? raw.confidence : null,
    coveredAt: asString(raw.coveredAt) ?? asString(raw.answeredAt) ?? null,
    evidenceTranscript: asString(raw.evidenceTranscript) ?? null,
    evidence: raw.evidence && typeof raw.evidence === 'object' ? raw.evidence as Record<string, unknown> : null,
    createdAt: asString(raw.createdAt) ?? '',
    updatedAt: asString(raw.updatedAt) ?? '',
  };
}

export const presentationAPI = {
  async createSession(
    deckId: string,
    prepSessionId: string,
    opts?: { projectId?: string; stakeholderProfileId?: string }
  ): Promise<PresentationSession> {
    const response = await apiClient.post('/api/interview-sessions/', {
      prepSessionId,
      documentId: deckId,
      ...(opts?.projectId && { projectId: opts.projectId }),
      ...(opts?.stakeholderProfileId && { stakeholderProfileId: opts.stakeholderProfileId }),
    });
    return response.data;
  },

  async getSession(sessionId: string): Promise<PresentationSession> {
    const response = await apiClient.get(`/api/interview-sessions/${sessionId}`);
    return response.data;
  },

  async updateSession(
    sessionId: string,
    data: Partial<PresentationSession>
  ): Promise<PresentationSession> {
    const response = await apiClient.patch(
      `/api/interview-sessions/${sessionId}`,
      data
    );
    return response.data;
  },

  async endSession(sessionId: string): Promise<PresentationSession> {
    const response = await apiClient.post(
      `/api/interview-sessions/${sessionId}/end`
    );
    return response.data;
  },

  async getSlides(deckId: string): Promise<Slide[]> {
    const response = await apiClient.get(`/api/documents/${deckId}/analysis`);
    const slides = Array.isArray(response.data.slides) ? response.data.slides : [];
    return slides.map((slide: ApiRecord) => normalizeSlide(slide));
  },

  async getDeckQuestionCards(deckId: string): Promise<QuestionCard[]> {
    const response = await apiClient.get(`/api/question-cards/document/${deckId}`);
    return response.data;
  },

  async getCardStates(sessionId: string): Promise<PresentationCardState[]> {
    const response = await apiClient.get(
      `/api/interview-sessions/${sessionId}/card-states`
    );
    const states = Array.isArray(response.data) ? response.data : [];
    return states.map((state: ApiRecord) => normalizeCardState(state));
  },

  async getSessionCards(sessionId: string, deckId: string): Promise<CardState[]> {
    const [cardStates, questionCards] = await Promise.all([
      this.getCardStates(sessionId),
      this.getDeckQuestionCards(deckId),
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
  ): Promise<PresentationCardState> {
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
    endedAt?: string
  ) {
    const response = await apiClient.post(
      `/api/interview-sessions/${sessionId}/utterances`,
      { transcript, themeId, sectionId: themeId, realtimeItemId, startedAt, endedAt }
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

  async generateOutputs(sessionId: string): Promise<{
    brd: { markdown: string; openIssuesCount: number }
    transcript: { markdown: string; utteranceCount: number }
  }> {
    const response = await apiClient.post(`/api/interview-sessions/${sessionId}/outputs/generate`);
    return response.data;
  }
};
