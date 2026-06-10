"""Interview Session models."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Numeric, Integer
from sqlalchemy.orm import relationship

from app.db.session import Base


class InterviewSession(Base):
    """InterviewSession model - represents an interview session."""

    __tablename__ = "interview_sessions"

    id = Column(String, primary_key=True)
    prep_session_id = Column(String, ForeignKey("prep_sessions.id"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="idle", index=True)  # idle, preparing, ready, interviewing, paused, ended, failed
    current_section_id = Column(String, ForeignKey("sections.id"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    paused_duration_seconds = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    prep_session = relationship("PrepSession", back_populates="interview_sessions")
    document = relationship("Document", back_populates="interview_sessions")
    user = relationship("User", back_populates="interview_sessions")
    card_states = relationship("InterviewCardState", back_populates="session", cascade="all, delete-orphan")
    utterances = relationship("Utterance", back_populates="session", cascade="all, delete-orphan")
    ai_usage_events = relationship("AIUsageEvent", back_populates="interview_session", cascade="all, delete-orphan")
    brd_draft = relationship("BRDDraft", back_populates="interview_session", uselist=False, cascade="all, delete-orphan")


class InterviewCardState(Base):
    """InterviewCardState model - tracks question card state during an interview session."""

    __tablename__ = "interview_card_states"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    question_card_id = Column(String, ForeignKey("question_cards.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="pending")  # pending, listening, probably_sufficient, sufficient, at_risk, skipped, manually_checked, disabled
    confidence = Column(Numeric(4, 3), nullable=True)
    answered_at = Column(DateTime, nullable=True)
    evidence_transcript = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    session = relationship("InterviewSession", back_populates="card_states")
    question_card = relationship("QuestionCard", back_populates="card_states")
