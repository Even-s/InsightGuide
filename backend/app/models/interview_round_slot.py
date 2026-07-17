"""Many-to-many assignment between interview rounds and covered role slots."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base


class InterviewRoundSlot(Base):
    """A role slot intentionally covered by one interview round."""

    __tablename__ = "interview_round_slots"
    __table_args__ = (UniqueConstraint("round_id", "slot_id", name="uq_interview_round_slot"),)

    id = Column(String, primary_key=True)
    round_id = Column(
        String, ForeignKey("interview_rounds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_id = Column(
        String, ForeignKey("stakeholder_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    interview_round = relationship("InterviewRound", back_populates="slot_assignments")
    slot = relationship("StakeholderSlot")
