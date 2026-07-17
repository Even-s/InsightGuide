"""Many-to-many source role mapping for question cards."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base


class QuestionCardSlot(Base):
    """Role slot source for a question card.

    A generated card can satisfy one or more stakeholder-role perspectives.
    This table is the clean source of truth for card-to-role attribution.
    """

    __tablename__ = "question_card_slots"
    __table_args__ = (
        UniqueConstraint("question_card_id", "slot_id", name="uq_question_card_slot"),
    )

    id = Column(String, primary_key=True)
    question_card_id = Column(
        String, ForeignKey("question_cards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_id = Column(
        String, ForeignKey("stakeholder_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    question_card = relationship("QuestionCard", back_populates="slot_sources")
    slot = relationship("StakeholderSlot")
