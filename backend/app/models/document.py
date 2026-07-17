"""Document model."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class Document(Base):
    """Document model - represents an interview guide document."""

    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(
        String, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stakeholder_profile_id = Column(
        String, ForeignKey("stakeholder_profiles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    interview_round_id = Column(
        String, ForeignKey("interview_rounds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    guide_version = Column(Integer, nullable=False, default=1)
    is_frozen = Column(Boolean, nullable=False, default=False, index=True)
    title = Column(String, nullable=False)
    source_file_url = Column(Text, nullable=False)
    file_type = Column(String, nullable=False)  # pdf, docx, md, txt
    status = Column(
        String, nullable=False, default="uploaded", index=True
    )  # uploaded, analyzing, analyzed, failed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Interview plan metadata (populated by AI after theme generation)
    interview_objective = Column(Text, nullable=True)
    interview_priority_order = Column(JSONB, nullable=True)
    interview_priority_reasoning = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="documents")
    project = relationship("Project", back_populates="documents", foreign_keys=[project_id])
    interview_round = relationship(
        "InterviewRound",
        back_populates="documents",
        foreign_keys=[interview_round_id],
    )
    interview_themes = relationship(
        "InterviewTheme", back_populates="document", cascade="all, delete-orphan"
    )
    question_cards = relationship(
        "QuestionCard", back_populates="document", cascade="all, delete-orphan"
    )
    prep_sessions = relationship(
        "PrepSession", back_populates="document", cascade="all, delete-orphan"
    )
    interview_sessions = relationship(
        "InterviewSession", back_populates="document", cascade="all, delete-orphan"
    )
    ai_usage_events = relationship(
        "AIUsageEvent", back_populates="document", cascade="all, delete-orphan"
    )
