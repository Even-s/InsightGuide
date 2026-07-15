"""Live Utterance model - Realtime API transcripts during interview."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class LiveUtterance(Base):
    """LiveUtterance model - represents Realtime API transcripts during interview.

    These are the canonical transcript segments used for card coverage, reporting,
    and post-interview analysis.
    """

    __tablename__ = "live_utterances"

    id = Column(String, primary_key=True)
    session_id = Column(
        String,
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    realtime_event_id = Column(String, nullable=True)
    transcript = Column(Text, nullable=False)

    # Retained for API/database compatibility. New Realtime segments use one neutral source label.
    speaker = Column(String, nullable=False, default="realtime")

    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    sequence_index = Column(Integer, nullable=False)

    is_partial = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("InterviewSession", back_populates="live_utterances")
