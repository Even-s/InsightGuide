"""Pydantic schemas for API request/response models."""

# New InsightGuide schemas
from app.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentStatus,
    DocumentAnalysisResponse,
)
from app.schemas.section import (
    SectionResponse,
    SectionWithQuestionCards,
)
from app.schemas.question_card import (
    QuestionCardSchema,
    QuestionCardCreate,
    QuestionCardUpdate,
    CoverageRule,
    MustMentionElement,
    SufficiencyThresholds,
    SufficiencyEvidence,
)
from app.schemas.interview import (
    InterviewSessionSchema,
    InterviewSessionCreate,
    InterviewSessionUpdate,
    InterviewCardStateSchema,
    InterviewCardStateUpdate,
    UtteranceSchema,
    UtteranceCreate,
    InterviewSessionWithDocument,
    InterviewSessionListResponse,
)
from app.schemas.prep_session import (
    PrepSessionSchema,
    PrepSessionCreate,
    PrepSessionUpdate,
    PrepSessionWithDocument,
    PrepSessionListResponse,
)
from app.schemas.evaluation import (
    EvaluateAnswersInput,
    EvaluateAnswersOutput,
    AISemanticEvaluationInput,
    AISemanticEvaluationOutput,
    CandidateQuestionCard,
    SemanticDecision,
)

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
