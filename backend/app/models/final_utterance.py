"""Final Utterance model - formal diarized transcripts."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Float
from sqlalchemy.orm import relationship

from app.db.session import Base


class FinalUtterance(Base):
    """FinalUtterance model - represents formal diarized transcript segments.

    These are the authoritative transcripts used for:
    - BRD generation
    - Q/A reconstruction
    - Final card coverage
    - Formal reports
    """

    __tablename__ = "final_utterances"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    transcript_revision_id = Column(String, ForeignKey("transcript_revisions.id"), nullable=False, index=True)

    speaker_label = Column(String, nullable=False)
    # speaker_0 | speaker_1 | speaker_2 (original diarize labels)

    speaker_role = Column(String, nullable=True)
    # interviewer | interviewee | unknown (internal use for Q/A reconstruction)

    speaker_display_name = Column(String, nullable=True)
    # Speaker 1 | Speaker 2 (for report display)

    transcript = Column(Text, nullable=False)

    start_seconds = Column(Float, nullable=True)
    end_seconds = Column(Float, nullable=True)

    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    sequence_index = Column(Integer, nullable=False)

    theme_id = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("InterviewSession", back_populates="final_utterances")
    transcript_revision = relationship("TranscriptRevision", back_populates="final_utterances")
