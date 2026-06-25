"""BRD (Business Requirements Document) models."""

import enum
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class BRDStatus(str, enum.Enum):
    """BRD generation status."""

    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPORTED = "exported"


class RequirementType(str, enum.Enum):
    """Requirement classification."""

    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    BUSINESS = "business"
    USER = "user"
    TECHNICAL = "technical"


class RequirementPriority(str, enum.Enum):
    """Requirement priority level."""

    MUST_HAVE = "must_have"
    SHOULD_HAVE = "should_have"
    NICE_TO_HAVE = "nice_to_have"


class BRDDraft(Base):
    """BRD Draft model - represents a generated business requirements document."""

    __tablename__ = "brd_drafts"

    id = Column(String, primary_key=True)
    interview_session_id = Column(
        String, ForeignKey("interview_sessions.id"), nullable=False, unique=True, index=True
    )
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(SQLEnum(BRDStatus), nullable=False, default=BRDStatus.GENERATING, index=True)

    # BRD Content
    title = Column(String, nullable=True)
    executive_summary = Column(Text, nullable=True)
    project_overview = Column(Text, nullable=True)
    business_objectives = Column(JSON, nullable=True)  # List of objectives
    success_criteria = Column(JSON, nullable=True)  # List of criteria
    stakeholders = Column(JSON, nullable=True)  # List of stakeholders
    assumptions = Column(JSON, nullable=True)  # List of assumptions
    constraints = Column(JSON, nullable=True)  # List of constraints
    risks = Column(JSON, nullable=True)  # List of risks

    # Generation metadata
    generated_at = Column(DateTime, nullable=True)
    generation_duration_seconds = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    # Document export metadata
    markdown_content = Column(Text, nullable=True)
    last_exported_at = Column(DateTime, nullable=True)
    export_url = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="brd_drafts")
    interview_session = relationship("InterviewSession", back_populates="brd_draft")
    requirements = relationship(
        "Requirement", back_populates="brd_draft", cascade="all, delete-orphan"
    )


class Requirement(Base):
    """Requirement model - individual requirement extracted from interview."""

    __tablename__ = "requirements"

    id = Column(String, primary_key=True)
    brd_draft_id = Column(String, ForeignKey("brd_drafts.id"), nullable=False, index=True)

    # Requirement details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    type = Column(SQLEnum(RequirementType), nullable=False, index=True)
    priority = Column(
        SQLEnum(RequirementPriority),
        nullable=False,
        default=RequirementPriority.SHOULD_HAVE,
        index=True,
    )

    # Traceability
    source_question_card_id = Column(
        String, ForeignKey("question_cards.id"), nullable=True, index=True
    )
    source_utterance_ids = Column(JSON, nullable=True)  # List of utterance IDs
    confidence = Column(String, nullable=True)  # Confidence score from AI

    # User story
    user_story = Column(Text, nullable=True)  # "As a [user], I want [feature], so that [benefit]"
    acceptance_criteria = Column(JSON, nullable=True)  # List of criteria

    # Additional metadata
    rationale = Column(Text, nullable=True)
    dependencies = Column(JSON, nullable=True)  # List of requirement IDs
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    brd_draft = relationship("BRDDraft", back_populates="requirements")
    question_card = relationship("QuestionCard", back_populates="requirements")
