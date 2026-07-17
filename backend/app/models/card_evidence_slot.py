"""Role attribution snapshot for criterion evidence."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base


class CardEvidenceSlot(Base):
    """Attach one criterion-evidence row to the stakeholder roles it supports."""

    __tablename__ = "card_evidence_slots"
    __table_args__ = (UniqueConstraint("evidence_id", "slot_id", name="uq_card_evidence_slot"),)

    id = Column(String, primary_key=True)
    evidence_id = Column(
        String,
        ForeignKey("card_criterion_evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slot_id = Column(
        String, ForeignKey("stakeholder_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relevance = Column(Numeric(4, 3), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    evidence = relationship("CardCriterionEvidence", back_populates="slot_attributions")
    slot = relationship("StakeholderSlot")
