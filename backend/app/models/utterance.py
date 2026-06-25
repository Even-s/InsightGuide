"""Utterance model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Utterance(Base):
    """Utterance model - represents a transcribed speech segment during interview."""

    __tablename__ = "utterances"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    section_id = Column(String, ForeignKey("sections.id"), nullable=True, index=True)
    transcript = Column(Text, nullable=False)
    speaker = Column(String, nullable=False, default="interviewee")  # interviewer, interviewee
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    realtime_item_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    session = relationship("InterviewSession", back_populates="utterances")
    section = relationship("Section", back_populates="utterances")
