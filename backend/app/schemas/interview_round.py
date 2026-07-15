"""Schemas for interview topic series and repeated interview rounds."""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

GenerationMode = Literal["continue_unfinished", "follow_up", "validate", "new_scope"]


class InterviewSeriesCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    topicKey: Optional[str] = Field(default=None, max_length=80)


class InterviewSeriesResponse(BaseModel):
    id: str
    projectId: str
    stakeholderProfileId: str
    title: str
    topicKey: str
    status: str
    roundsCount: int = 0
    createdAt: datetime
    updatedAt: datetime


class InterviewRoundCreate(BaseModel):
    objective: Optional[str] = None
    generationMode: GenerationMode = "follow_up"
    sourceSessionIds: List[str] = Field(default_factory=list)
    focusTopics: List[str] = Field(default_factory=list)
    excludeCompletedQuestions: bool = True


class InterviewRoundGuideOptions(BaseModel):
    durationMinutes: int = Field(default=30, ge=10, le=90)
    interviewStyle: Optional[Literal["exploratory", "structured", "validation"]] = None
    excludeTopics: Optional[str] = None


class InterviewRoundSessionCreate(BaseModel):
    continueFromSessionId: Optional[str] = None


class InterviewRoundAggregateResponse(BaseModel):
    latestMemoId: Optional[str] = None
    sourceSessionIds: List[str] = Field(default_factory=list)
    coverageSnapshot: Dict = Field(default_factory=dict)
    evidenceSnapshot: List[Dict] = Field(default_factory=list)
    status: str = "stale"
    version: int = 0
    generatedAt: Optional[datetime] = None
    invalidatedAt: Optional[datetime] = None


class InterviewRoundResponse(BaseModel):
    id: str
    seriesId: str
    roundNumber: int
    objective: Optional[str]
    generationMode: str
    sourceSessionIds: List[str]
    focusTopics: List[str]
    excludeCompletedQuestions: bool
    guideDocumentId: Optional[str]
    guideVersion: Optional[int] = None
    cardCount: int = 0
    status: str
    sessionIds: List[str] = Field(default_factory=list)
    aggregate: Optional[InterviewRoundAggregateResponse] = None
    createdAt: datetime
    updatedAt: datetime


class InterviewRoundGuideResponse(BaseModel):
    documentId: str
    prepSessionId: str
    seriesId: str
    roundId: str
    roundNumber: int
    cardCount: int
    status: str
    themes: List[Dict]
