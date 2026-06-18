"""Utterance alignment model - Phase 5

Maps live_utterances (Realtime API) to final_utterances (diarized) for traceability.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, ForeignKey
from app.db.session import Base


class UtteranceAlignment(Base):
    """Maps live (Realtime API) utterances to final (diarized) utterances."""

    __tablename__ = "utterance_alignment"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    live_utterance_id = Column(String, ForeignKey("live_utterances.id"), nullable=True)
    final_utterance_id = Column(String, ForeignKey("final_utterances.id"), nullable=True)
    transcript_revision_id = Column(String, ForeignKey("transcript_revisions.id"), nullable=False)
    time_overlap_score = Column(Float, nullable=True)
    text_similarity_score = Column(Float, nullable=True)
    alignment_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
