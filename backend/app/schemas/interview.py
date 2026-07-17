"""Interview session Pydantic schemas."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.question_card import QuestionCardSchema


class InterviewSessionSchema(BaseModel):
    """Interview session schema."""

    id: str
    prepSessionId: str
    documentId: str
    userId: str
    projectId: Optional[str] = None
    stakeholderProfileId: Optional[str] = None
    interviewRoundId: Optional[str] = None
    continuedFromSessionId: Optional[str] = None
    status: Literal[
        "idle",
        "preparing",
        "ready",
        "interviewing",
        "paused",
        "recovering",
        "ended",
        "failed",
    ]
    currentThemeId: Optional[str] = None
    activeCardId: Optional[str] = None
    startedAt: Optional[datetime] = None
    endedAt: Optional[datetime] = None
    pausedAt: Optional[datetime] = None
    pausedDurationSeconds: int = 0
    createdAt: datetime
    costUsd: float = 0.0
    aiUsage: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class InterviewSessionCreate(BaseModel):
    """Schema for creating an interview session."""

    model_config = ConfigDict(extra="forbid")

    prepSessionId: str
    documentId: str
    projectId: Optional[str] = None
    stakeholderProfileId: Optional[str] = None
    interviewRoundId: Optional[str] = None
    continueFromSessionId: Optional[str] = None


class InterviewSessionUpdate(BaseModel):
    """Schema for updating an interview session."""

    model_config = ConfigDict(extra="forbid")

    status: Optional[
        Literal[
            "idle",
            "preparing",
            "ready",
            "interviewing",
            "paused",
            "recovering",
            "ended",
            "failed",
        ]
    ] = None
    currentThemeId: Optional[str] = None


class InterviewCardStateUpdate(BaseModel):
    """Schema for manually updating an interview card state."""

    status: Literal[
        "pending",
        "listening",
        "probably_sufficient",
        "sufficient",
        "at_risk",
        "skipped",
        "manually_checked",
        "disabled",
        "not_applicable_for_role",
        "needs_different_stakeholder",
    ]
    confidence: Optional[float] = Field(None, ge=0, le=1)
    evidenceTranscript: Optional[str] = None
    evidence: Optional[dict] = None


class InterviewCardStateSchema(BaseModel):
    """Interview card state schema."""

    id: str
    sessionId: str
    questionCardId: str
    status: Literal[
        "pending",
        "listening",
        "probably_sufficient",
        "sufficient",
        "at_risk",
        "skipped",
        "manually_checked",
        "disabled",
        "not_applicable_for_role",
        "needs_different_stakeholder",
    ]
    confidence: Optional[float] = Field(None, ge=0, le=1)
    answeredAt: Optional[datetime] = None
    evidenceTranscript: Optional[str] = None
    evidence: Optional[dict] = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class SessionQuestionCardStateSchema(BaseModel):
    """Single endpoint response for card runtime state plus question metadata."""

    stateId: str
    sessionId: str
    questionCardId: str
    status: Literal[
        "pending",
        "listening",
        "probably_sufficient",
        "sufficient",
        "at_risk",
        "skipped",
        "manually_checked",
        "disabled",
        "not_applicable_for_role",
        "needs_different_stakeholder",
    ]
    confidence: Optional[float] = Field(None, ge=0, le=1)
    activationScore: float = 0.0
    completionScore: float = 0.0
    completionSource: Optional[str] = None
    manualNote: Optional[str] = None
    answeredAt: Optional[datetime] = None
    evidenceTranscript: Optional[str] = None
    evidence: Optional[dict] = None
    createdAt: datetime
    updatedAt: datetime
    questionCard: QuestionCardSchema


class UtteranceSchema(BaseModel):
    """Utterance schema."""

    id: str
    sessionId: str
    themeId: Optional[str] = None
    askedCardIds: List[str] = Field(default_factory=list)
    transcript: str
    startedAt: Optional[datetime] = None
    endedAt: Optional[datetime] = None
    realtimeItemId: Optional[str] = None
    createdAt: datetime

    class Config:
        from_attributes = True


class UtteranceCreate(BaseModel):
    """Schema for creating an utterance."""

    model_config = ConfigDict(extra="forbid")

    transcript: str
    themeId: Optional[str] = None
    startedAt: Optional[datetime] = None
    endedAt: Optional[datetime] = None
    realtimeItemId: Optional[str] = None
    askedCardIds: Optional[List[str]] = None


class InterviewSessionWithDocument(BaseModel):
    """Interview session with document information."""

    id: str
    prepSessionId: str
    documentId: str
    documentTitle: str
    userId: str
    projectId: Optional[str] = None
    stakeholderProfileId: Optional[str] = None
    interviewRoundId: Optional[str] = None
    continuedFromSessionId: Optional[str] = None
    status: Literal[
        "idle",
        "preparing",
        "ready",
        "interviewing",
        "paused",
        "recovering",
        "ended",
        "failed",
    ]
    currentThemeId: Optional[str] = None
    startedAt: Optional[datetime] = None
    endedAt: Optional[datetime] = None
    pausedAt: Optional[datetime] = None
    pausedDurationSeconds: int = 0
    createdAt: datetime
    duration: Optional[int] = None
    costUsd: float = 0.0
    aiUsage: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class InterviewSessionListResponse(BaseModel):
    """Response schema for session list with pagination."""

    sessions: List[InterviewSessionWithDocument]
    total: int
    limit: int
    offset: int
