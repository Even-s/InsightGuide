"""Question Answer model - records actual answers provided during interview."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship

from app.db.session import Base


class QuestionAnswer(Base):
    """QuestionAnswer model - represents an answer to a question asked during the interview.

    Each QuestionInstance can have one or more answers (e.g., if the interviewee
    elaborates across multiple utterances or the question is revisited later).
    """

    __tablename__ = "question_answers"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    question_instance_id = Column(String, ForeignKey("question_instances.id"), nullable=False, index=True)

    answer_text = Column(Text, nullable=True)
    answer_summary = Column(Text, nullable=True)

    answer_utterance_ids = Column(JSON, nullable=True, default=list)
    evidence_quotes = Column(JSON, nullable=True, default=list)

    answer_status = Column(String, nullable=True)
    # answered | partially_answered | not_answered | unclear

    confidence = Column(Float, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    question_instance = relationship("QuestionInstance", back_populates="answers")
