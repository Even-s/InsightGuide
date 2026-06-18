"""Live Utterance model - Realtime API transcripts during interview."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Boolean
from sqlalchemy.orm import relationship

from app.db.session import Base


class LiveUtterance(Base):
    """LiveUtterance model - represents Realtime API transcripts during interview.

    These are used for provisional card coverage and immediate feedback during the interview.
    They are NOT deleted after diarization and serve as the basis for live evaluation.
    """

    __tablename__ = "live_utterances"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)

    realtime_event_id = Column(String, nullable=True)
    transcript = Column(Text, nullable=False)

    speaker = Column(String, default='unknown')
    # During the interview we don't do speaker identification, all marked as unknown or interviewee

    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    sequence_index = Column(Integer, nullable=False)

    is_partial = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("InterviewSession", back_populates="live_utterances")
