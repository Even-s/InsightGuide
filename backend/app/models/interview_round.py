"""Interview round model for immutable, versioned stakeholder interviews."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class InterviewRound(Base):
    """One planned interview round inside an interview series."""

    __tablename__ = "interview_rounds"
    __table_args__ = (
        UniqueConstraint("series_id", "round_number", name="uq_interview_round_series_number"),
    )

    id = Column(String, primary_key=True)
    series_id = Column(
        String,
        ForeignKey("interview_series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_number = Column(Integer, nullable=False)
    objective = Column(Text, nullable=True)
    generation_mode = Column(String, nullable=False, default="follow_up")
    source_session_ids = Column(JSON, nullable=False, default=list)
    focus_topics = Column(JSON, nullable=False, default=list)
    exclude_completed_questions = Column(Boolean, nullable=False, default=True)
    guide_document_id = Column(
        String,
        ForeignKey(
            "documents.id",
            name="interview_rounds_guide_document_id_fkey",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
        index=True,
    )
    status = Column(String, nullable=False, default="draft", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    series = relationship("InterviewSeries", back_populates="rounds")
    guide_document = relationship(
        "Document",
        foreign_keys=[guide_document_id],
        post_update=True,
    )
    documents = relationship(
        "Document",
        back_populates="interview_round",
        foreign_keys="Document.interview_round_id",
    )
    interview_sessions = relationship("InterviewSession", back_populates="interview_round")
    insight_memos = relationship("InterviewInsightMemo", back_populates="interview_round")
    aggregate = relationship(
        "InterviewRoundAggregate",
        back_populates="interview_round",
        uselist=False,
        cascade="all, delete-orphan",
    )
    slot_assignments = relationship(
        "InterviewRoundSlot",
        back_populates="interview_round",
        cascade="all, delete-orphan",
    )
