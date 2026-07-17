"""Answer evaluation engine Pydantic schemas."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class EvaluateAnswersInput(BaseModel):
    """Input for answer sufficiency evaluation."""

    sessionId: str
    themeId: str
    utteranceId: str
    transcript: str
    questionCardIds: List[str]


class QuestionCardMatch(BaseModel):
    """Result of evaluating answer sufficiency for a single question card."""

    questionCardId: str
    semanticScore: float = Field(ge=0, le=1)
    keywordScore: float = Field(ge=0, le=1)
    elementScore: float = Field(ge=0, le=1)
    finalScore: float = Field(ge=0, le=1)
    decision: Literal["insufficient", "probably_sufficient", "sufficient"]
    reason: str


class EvaluateAnswersOutput(BaseModel):
    """Output from answer sufficiency evaluation."""

    sessionId: str
    themeId: str
    utteranceId: str
    transcript: str
    matches: List[QuestionCardMatch]


class CandidateQuestionCard(BaseModel):
    """Candidate question card for AI semantic evaluation."""

    id: str
    questionText: str
    questionType: Literal[
        "clarification", "validation", "exploration", "edge_case", "constraint", "priority"
    ]
    importance: Literal["must", "should"]
    semanticAnchors: List[str]
    expectedKeywords: List[str]
    expectedAnswerElements: List[str]
    currentStatus: Literal["pending", "listening", "probably_sufficient", "at_risk"]


class Utterance(BaseModel):
    """Utterance for semantic evaluation."""

    id: str
    transcript: str
    startedAt: Optional[datetime] = None
    endedAt: Optional[datetime] = None


class AISemanticEvaluationInput(BaseModel):
    """Input for AI semantic evaluation."""

    sessionId: str
    themeId: str
    utterance: Utterance
    candidateCards: List[CandidateQuestionCard]


class SemanticDecision(BaseModel):
    """Decision from AI semantic evaluation for a single card."""

    questionCardId: str
    answerSufficiency: Literal["insufficient", "partially_sufficient", "sufficient"]
    semanticScore: float = Field(ge=0, le=1)
    coveredElements: List[str]
    missingElements: List[str]
    evidenceQuote: str
    reason: str


class AISemanticEvaluationOutput(BaseModel):
    """Output from AI semantic evaluation."""

    sessionId: str
    themeId: str
    utteranceId: str
    decisions: List[SemanticDecision]
