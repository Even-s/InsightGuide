"""Interview session Pydantic schemas."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class InterviewSessionSchema(BaseModel):
    """Interview session schema."""

    id: str
    prepSessionId: str
    documentId: str
    userId: str
    status: Literal[
        "idle",
        "preparing",
        "ready",
        "interviewing",
        "paused",
        "section_transitioning",
        "recovering",
        "ended",
        "failed",
    ]
    currentSectionId: Optional[str] = None
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

    prepSessionId: str
    documentId: str
    projectId: Optional[str] = None
    stakeholderProfileId: Optional[str] = None


class InterviewSessionUpdate(BaseModel):
    """Schema for updating an interview session."""

    status: Optional[
        Literal[
            "idle",
            "preparing",
            "ready",
            "interviewing",
            "paused",
            "section_transitioning",
            "recovering",
            "ended",
            "failed",
        ]
    ] = None
    currentSectionId: Optional[str] = None


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


class UtteranceSchema(BaseModel):
    """Utterance schema."""

    id: str
    sessionId: str
    sectionId: Optional[str] = None
    speaker: Literal["interviewer", "interviewee"] = "interviewee"
    transcript: str
    startedAt: Optional[datetime] = None
    endedAt: Optional[datetime] = None
    realtimeItemId: Optional[str] = None
    createdAt: datetime

    class Config:
        from_attributes = True


class UtteranceCreate(BaseModel):
    """Schema for creating an utterance."""

    transcript: str
    themeId: Optional[str] = None
    sectionId: Optional[str] = None
    speaker: Literal["interviewer", "interviewee"] = "interviewee"
    startedAt: Optional[datetime] = None
    endedAt: Optional[datetime] = None
    realtimeItemId: Optional[str] = None
    askedCardId: Optional[str] = None


class PartialTranscriptMatchCreate(BaseModel):
    """Schema for streaming partial transcript matching."""

    transcript: str = Field(min_length=1, max_length=4000)
    themeId: Optional[str] = None
    sectionId: Optional[str] = None
    speaker: Literal["interviewer", "interviewee"] = "interviewee"
    realtimeItemId: Optional[str] = None
    activeCardId: Optional[str] = None


class InterviewSessionWithDocument(BaseModel):
    """Interview session with document information."""

    id: str
    prepSessionId: str
    documentId: str
    documentTitle: str
    userId: str
    projectId: Optional[str] = None
    stakeholderProfileId: Optional[str] = None
    status: Literal[
        "idle",
        "preparing",
        "ready",
        "interviewing",
        "paused",
        "section_transitioning",
        "recovering",
        "ended",
        "failed",
    ]
    currentSectionId: Optional[str] = None
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
