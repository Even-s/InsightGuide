"""Question Instance model - records actual questions asked during interview."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class QuestionInstance(Base):
    """QuestionInstance model - represents an actual question asked during the interview.

    This differs from QuestionCard (which represents planned questions).
    QuestionInstance captures what was actually asked, including follow-ups and variations.
    """

    __tablename__ = "question_instances"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)

    source_question_id = Column(String, nullable=True)
    # maps to original card or interview guide question

    theme_id = Column(String, nullable=True)
    card_id = Column(String, ForeignKey("question_cards.id"), nullable=True)

    interviewer_utterance_id = Column(String, ForeignKey("final_utterances.id"), nullable=True)
    asked_text = Column(Text, nullable=False)

    normalized_question = Column(Text, nullable=True)

    question_type = Column(String, nullable=True)
    # main_question | follow_up | clarification

    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    sequence_index = Column(Integer, nullable=True)
    match_confidence = Column(Float, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    answers = relationship("QuestionAnswer", back_populates="question_instance", cascade="all, delete-orphan")
