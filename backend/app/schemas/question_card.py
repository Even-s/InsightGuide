"""Question Card Pydantic schemas."""

from typing import Literal, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class MustMentionElement(BaseModel):
    """Element that must be mentioned for the answer to be considered sufficient."""
    text: str
    required: bool = True
    aliases: List[str] = Field(default_factory=list)
    subpoints: List[str] = Field(default_factory=list)


class ScoringWeights(BaseModel):
    """Weights for scoring algorithm."""
    semanticSimilarity: float = 0.55
    keywordCoverage: float = 0.25
    elementCoverage: float = 0.20


class SufficiencyThresholds(BaseModel):
    """Thresholds for sufficiency decisions."""
    probablySufficient: float = 0.62
    sufficient: float = 0.78


class CoverageRule(BaseModel):
    """Rules for determining if a question has been answered sufficiently."""
    semanticAnchors: List[str]
    expectedKeywords: List[str] = Field(default_factory=list)
    mustMentionElements: List[MustMentionElement] = Field(default_factory=list)
    negativeSignals: List[str] = Field(default_factory=list)
    thresholds: SufficiencyThresholds = Field(default_factory=SufficiencyThresholds)
    scoringWeights: ScoringWeights = Field(default_factory=ScoringWeights)


class SufficiencyEvidence(BaseModel):
    """Evidence of answer sufficiency."""
    matchedUtteranceIds: List[str] = Field(default_factory=list)
    matchedTranscript: Optional[str] = None
    matchedAt: Optional[datetime] = None
    semanticScore: Optional[float] = None
    keywordScore: Optional[float] = None
    elementScore: Optional[float] = None
    finalScore: Optional[float] = None


class CardUI(BaseModel):
    """UI-specific properties for question card."""
    color: Literal["default", "green", "yellow", "red", "gray"] = "default"
    isVisible: bool = True
    isPinned: bool = False
    displayMode: Literal["full", "compact", "hidden"] = "full"


class QuestionCardSchema(BaseModel):
    """Question Card schema."""
    id: str
    documentId: str
    sectionId: str
    sectionNumber: int = Field(ge=1)
    questionText: str = Field(min_length=1, max_length=200)
    questionType: Literal[
        "clarification", "validation", "exploration",
        "edge_case", "constraint", "priority"
    ] = "clarification"
    importance: Literal["must", "should"]
    coverageRule: CoverageRule
    suggestedFollowup: Optional[str] = Field(None, max_length=2000)
    expectedAnswerElements: List[str] = Field(default_factory=list)
    estimatedSeconds: int = Field(default=30, ge=5, le=300)
    orderIndex: int = Field(default=0, ge=0)
    status: Literal[
        "pending", "listening", "probably_sufficient", "sufficient",
        "at_risk", "skipped", "manually_checked", "disabled"
    ] = "pending"
    confidence: Optional[float] = Field(None, ge=0, le=1)
    evidence: Optional[SufficiencyEvidence] = None
    ui: Optional[CardUI] = None
    createdBy: Literal["ai", "user", "system"] = "ai"
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class QuestionCardCreate(BaseModel):
    """Schema for creating a question card (simplified - user provides question and importance)."""
    sectionId: Optional[str] = Field(None, alias="sectionId")
    slideId: Optional[str] = Field(None)
    questionText: Optional[str] = Field(None, min_length=1, max_length=200)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    suggestedFollowup: Optional[str] = Field(None, min_length=1, max_length=2000)
    suggestedScript: Optional[str] = Field(None, min_length=1, max_length=2000)
    importance: Literal["must", "should"] = "must"

    # Optional - AI will generate if not provided
    questionType: Optional[Literal[
        "clarification", "validation", "exploration",
        "edge_case", "constraint", "priority"
    ]] = None
    topicType: Optional[Literal[
        "clarification", "validation", "exploration",
        "edge_case", "constraint", "priority"
    ]] = None
    coverageRule: Optional[CoverageRule] = None
    expectedAnswerElements: Optional[List[str]] = None
    estimatedSeconds: Optional[int] = Field(None, ge=5, le=300)

    class Config:
        populate_by_name = True

    @property
    def resolved_section_id(self) -> str:
        return self.sectionId or self.slideId or ""

    @property
    def resolved_question_text(self) -> str:
        return self.questionText or self.title or "Untitled Question"

    @property
    def resolved_followup(self) -> str:
        return self.suggestedFollowup or self.suggestedScript or "Could you elaborate on that?"

    @property
    def resolved_question_type(self) -> Optional[str]:
        return self.questionType or self.topicType


class QuestionCardUpdate(BaseModel):
    """Schema for updating a question card."""
    questionText: Optional[str] = Field(None, min_length=1, max_length=200)
    suggestedFollowup: Optional[str] = Field(None, max_length=2000)
    importance: Optional[Literal["must", "should"]] = None
    questionType: Optional[Literal[
        "clarification", "validation", "exploration",
        "edge_case", "constraint", "priority"
    ]] = None
    coverageRule: Optional[CoverageRule] = None
    expectedAnswerElements: Optional[List[str]] = None
    estimatedSeconds: Optional[int] = Field(None, ge=5, le=300)
    orderIndex: Optional[int] = Field(None, ge=0)


class QuestionCardFollowupCleanupRequest(BaseModel):
    """Request for cleaning speech-transcribed question content."""
    text: str = Field(min_length=1, max_length=4000)


class QuestionCardFollowupCleanupResponse(BaseModel):
    """Cleaned speech-transcribed question content."""
    cleanedText: str
