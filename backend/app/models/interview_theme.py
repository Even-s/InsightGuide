"""InterviewTheme model — logical interview topic units derived from AI analysis."""

from datetime import datetime

from sqlalchemy import ARRAY, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class InterviewTheme(Base):
    """Represents a logical interview topic unit.

    Sits between Document and QuestionCard in the hierarchy:
      Document → InterviewTheme[] → QuestionCard[]

    Each theme groups related interview questions under a coherent topic
    (e.g. "現行作業流程", "客戶條件與排序依據") with rationale explaining
    why the topic needs to be explored during the interview.
    """

    __tablename__ = "interview_themes"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)

    theme_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    rationale = Column(Text, nullable=False, default="")
    brd_mapping = Column(ARRAY(String), nullable=True, server_default="{}")
    priority = Column(Integer, nullable=False, default=99)
    estimated_minutes = Column(Integer, nullable=True)

    order_index = Column(Integer, nullable=False, default=0)
    is_required = Column(Boolean, nullable=False, default=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    user_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="interview_themes")
    question_cards = relationship(
        "QuestionCard",
        back_populates="interview_theme",
        cascade="all, delete-orphan",
        foreign_keys="QuestionCard.interview_theme_id",
    )
