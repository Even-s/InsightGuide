"""Interview Session models."""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class InterviewSession(Base):
    """InterviewSession model - represents an interview session."""

    __tablename__ = "interview_sessions"

    id = Column(String, primary_key=True)
    prep_session_id = Column(String, ForeignKey("prep_sessions.id"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(
        String, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stakeholder_profile_id = Column(
        String,
        ForeignKey("stakeholder_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    interview_round_id = Column(
        String,
        ForeignKey("interview_rounds.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    continued_from_session_id = Column(
        String,
        ForeignKey("interview_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    interview_objective = Column(Text, nullable=True)
    status = Column(
        String, nullable=False, default="idle", index=True
    )  # idle, preparing, ready, interviewing, paused, ended, failed
    current_theme_id = Column(String, ForeignKey("interview_themes.id"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    paused_duration_seconds = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Active card routing — which card is currently being discussed
    active_card_id = Column(String, nullable=True)
    active_card_source = Column(
        String, nullable=True
    )  # system_suggested | user_confirmed | manual_selected | cleared
    active_card_confirmed_at = Column(DateTime, nullable=True)
    pending_answer_buffer = Column(
        JSONB, nullable=True
    )  # list of utterance_ids waiting for card confirmation

    # Relationships
    prep_session = relationship("PrepSession", back_populates="interview_sessions")
    document = relationship("Document", back_populates="interview_sessions")
    user = relationship("User", back_populates="interview_sessions")
    project = relationship(
        "Project", back_populates="interview_sessions", foreign_keys=[project_id]
    )
    stakeholder_profile = relationship(
        "StakeholderProfile",
        back_populates="interview_sessions",
        foreign_keys=[stakeholder_profile_id],
    )
    interview_round = relationship("InterviewRound", back_populates="interview_sessions")
    card_states = relationship(
        "InterviewCardState", back_populates="session", cascade="all, delete-orphan"
    )
    live_utterances = relationship(
        "LiveUtterance", back_populates="session", cascade="all, delete-orphan"
    )
    ai_usage_events = relationship(
        "AIUsageEvent", back_populates="interview_session", cascade="all, delete-orphan"
    )
    interview_brief = relationship(
        "InterviewBrief", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    insight_memo = relationship(
        "InterviewInsightMemo",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )

class InterviewCardState(Base):
    """InterviewCardState model - tracks question card state during an interview session."""

    __tablename__ = "interview_card_states"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    question_card_id = Column(String, ForeignKey("question_cards.id"), nullable=False, index=True)
    status = Column(
        String, nullable=False, default="pending"
    )  # pending, listening, probably_sufficient, sufficient, at_risk, skipped, manually_checked, disabled
    confidence = Column(Numeric(4, 3), nullable=True)
    activation_score = Column(Numeric(4, 3), nullable=False, server_default="0")
    completion_score = Column(Numeric(4, 3), nullable=False, server_default="0")
    completion_source = Column(String, nullable=True)  # ai | manual
    manual_note = Column(Text, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    evidence_transcript = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    session = relationship("InterviewSession", back_populates="card_states")
    question_card = relationship("QuestionCard", back_populates="card_states")
