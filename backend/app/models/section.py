"""Section model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Section(Base):
    """Section model - represents a section in a requirements document."""

    __tablename__ = "sections"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    section_number = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    extracted_text = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="sections")
    question_cards = relationship(
        "QuestionCard", back_populates="section", cascade="all, delete-orphan"
    )
    utterances = relationship("Utterance", back_populates="section")
