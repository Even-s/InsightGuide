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
    section_id = Column(String, ForeignKey("sections.id"), nullable=False, index=True)
    section_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String, nullable=False, default="clarification")  # clarification, validation, exploration, edge_case, constraint, priority
    importance = Column(String, nullable=False)  # must, should, optional
    coverage_rule = Column(JSON, nullable=False)
    suggested_followup = Column(Text, nullable=True)
    expected_answer_elements = Column(ARRAY(Text), nullable=True)
    estimated_seconds = Column(Integer, nullable=False, default=60)
    order_index = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="pending", index=True)  # pending, listening, probably_sufficient, sufficient, at_risk, skipped, manually_checked, disabled
    confidence = Column(Numeric(4, 3), nullable=True, default=0)
    ui = Column(JSON, nullable=True)
    created_by = Column(String, nullable=False, default="ai")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="question_cards")
    section = relationship("Section", back_populates="question_cards")
    card_states = relationship("InterviewCardState", back_populates="question_card")
    requirements = relationship("Requirement", back_populates="question_card")
