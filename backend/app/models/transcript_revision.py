"""Transcript Revision model - manages formal transcript versions."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship

from app.db.session import Base


class TranscriptRevision(Base):
    """TranscriptRevision model - manages formal transcript versions.

    Each diarization creates a new revision. This supports:
    - Re-diarization
    - Manual corrections
    - Version comparison
    """

    __tablename__ = "transcript_revisions"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)

    source = Column(String, nullable=False)
    # diarized | manual_upload | corrected

    model = Column(String, nullable=True)
    # e.g., gpt-4o-transcribe

    status = Column(String, nullable=False)
    # processing | completed | failed | superseded

    recording_started_at = Column(DateTime, nullable=True)
    audio_file_url = Column(Text, nullable=True)

    segment_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    session = relationship("InterviewSession", back_populates="transcript_revisions", foreign_keys=[session_id])
    final_utterances = relationship("FinalUtterance", back_populates="transcript_revision", cascade="all, delete-orphan")
