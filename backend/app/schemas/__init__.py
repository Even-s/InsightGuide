"""Pydantic schemas for API request/response models."""

# New InsightGuide schemas
from app.schemas.document import (
    DocumentAnalysisResponse,
    DocumentCreate,
    DocumentResponse,
    DocumentStatus,
)
from app.schemas.evaluation import (
    AISemanticEvaluationInput,
    AISemanticEvaluationOutput,
    CandidateQuestionCard,
    EvaluateAnswersInput,
    EvaluateAnswersOutput,
    SemanticDecision,
)
from app.schemas.interview import (
    InterviewCardStateSchema,
    InterviewCardStateUpdate,
    InterviewSessionCreate,
    InterviewSessionListResponse,
    InterviewSessionSchema,
    InterviewSessionUpdate,
    InterviewSessionWithDocument,
    UtteranceCreate,
    UtteranceSchema,
)
from app.schemas.prep_session import (
    PrepSessionCreate,
    PrepSessionListResponse,
    PrepSessionSchema,
    PrepSessionUpdate,
    PrepSessionWithDocument,
)
from app.schemas.question_card import (
    CoverageRule,
    MustMentionElement,
    QuestionCardCreate,
    QuestionCardSchema,
    QuestionCardUpdate,
    SufficiencyEvidence,
    SufficiencyThresholds,
)
from app.schemas.section import SectionResponse, SectionWithQuestionCards

__all__ = [
    # New InsightGuide schemas
    "DocumentCreate",
    "DocumentResponse",
    "DocumentStatus",
    "DocumentAnalysisResponse",
    "SectionResponse",
    "SectionWithQuestionCards",
    "QuestionCardSchema",
    "QuestionCardCreate",
    "QuestionCardUpdate",
    "CoverageRule",
    "MustMentionElement",
    "SufficiencyThresholds",
    "SufficiencyEvidence",
    "InterviewSessionSchema",
    "InterviewSessionCreate",
    "InterviewSessionUpdate",
    "InterviewCardStateSchema",
    "InterviewCardStateUpdate",
    "UtteranceSchema",
    "UtteranceCreate",
    "InterviewSessionWithDocument",
    "InterviewSessionListResponse",
    "PrepSessionSchema",
    "PrepSessionCreate",
    "PrepSessionUpdate",
    "PrepSessionWithDocument",
    "PrepSessionListResponse",
    "EvaluateAnswersInput",
    "EvaluateAnswersOutput",
    "AISemanticEvaluationInput",
    "AISemanticEvaluationOutput",
    "CandidateQuestionCard",
    "SemanticDecision",
]
