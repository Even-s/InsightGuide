"""Question Card model."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, Numeric, ARRAY
from sqlalchemy.orm import relationship

from app.db.session import Base


class QuestionCard(Base):
    """QuestionCard model - represents an interview question for a document section."""

    __tablename__ = "question_cards"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    interview_theme_id = Column(String, ForeignKey("interview_themes.id"), nullable=True, index=True)
    section_id = Column(String, ForeignKey("sections.id"), nullable=True, index=True)
    section_number = Column(Integer, nullable=True)

    focus_text = Column(Text, nullable=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String, nullable=False, default="clarification")
    importance = Column(String, nullable=False)  # must, should
    coverage_rule = Column(JSON, nullable=False)
    suggested_followup = Column(Text, nullable=True)
    expected_answer_elements = Column(ARRAY(Text), nullable=True)
    brd_mapping = Column(ARRAY(String), nullable=True)
    estimated_seconds = Column(Integer, nullable=False, default=90)
    order_index = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="pending", index=True)
    confidence = Column(Numeric(4, 3), nullable=True, default=0)
    ui = Column(JSON, nullable=True)
    created_by = Column(String, nullable=False, default="ai")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="question_cards")
    section = relationship("Section", back_populates="question_cards")
    interview_theme = relationship("InterviewTheme", back_populates="question_cards", foreign_keys=[interview_theme_id])
    card_states = relationship("InterviewCardState", back_populates="question_card", cascade="all, delete-orphan", passive_deletes=True)
    requirements = relationship("Requirement", back_populates="question_card", cascade="all, delete-orphan", passive_deletes=True)
