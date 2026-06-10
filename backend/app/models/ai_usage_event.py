"""AI usage accounting models."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base


class AIUsageEvent(Base):
    """Durable record of a billable AI usage event."""

    __tablename__ = "ai_usage_events"
    __table_args__ = (
        UniqueConstraint(
            "interview_session_id",
            "operation",
            "source_id",
            name="uq_ai_usage_event_source",
        ),
        UniqueConstraint(
            "document_id",
            "operation",
            "source_id",
            name="uq_ai_usage_event_document_source",
        ),
    )

    id = Column(String, primary_key=True)
    interview_session_id = Column(
        String,
        ForeignKey("interview_sessions.id"),
        nullable=True,
        index=True,
    )
    document_id = Column(String, ForeignKey("documents.id"), nullable=True, index=True)
    operation = Column(String, nullable=False, index=True)
    source_id = Column(String, nullable=True, index=True)
    model = Column(String, nullable=False, index=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    cached_input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    audio_seconds = Column(Numeric(10, 3), nullable=False, default=0)
    cost_usd = Column(Numeric(12, 6), nullable=False, default=0)
    pricing = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    interview_session = relationship("InterviewSession", back_populates="ai_usage_events")
    document = relationship("Document", back_populates="ai_usage_events")
