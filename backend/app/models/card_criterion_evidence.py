"""Card Criterion Evidence - append-only evidence ledger for card coverage."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class CardCriterionEvidence(Base):
    """Append-only record of evidence for a specific criterion on a card.

    Each row represents one piece of evidence extracted from an evaluation turn.
    Card state is derived by reducing all evidence rows for a (session, card) pair.
    """

    __tablename__ = "card_criterion_evidence"
    __table_args__ = (
        Index("ix_cce_session_card", "session_id", "card_id"),
        Index("ix_cce_session_card_criterion", "session_id", "card_id", "criterion_id"),
    )

    id = Column(String, primary_key=True)
    session_id = Column(
        String, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    card_id = Column(
        String, ForeignKey("question_cards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criterion_id = Column(String, nullable=False, index=True)
    utterance_id = Column(
        String, ForeignKey("live_utterances.id", ondelete="SET NULL"), nullable=True
    )
    evaluation_turn_text = Column(Text, nullable=True)
    status = Column(String, nullable=False)
    evidence_quote = Column(Text, nullable=True)
    normalized_value = Column(Text, nullable=True)
    evaluator_confidence = Column(Numeric(4, 3), nullable=True)
    reason = Column(Text, nullable=True)
    model = Column(String, nullable=False)
    evaluation_seq = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    slot_attributions = relationship(
        "CardEvidenceSlot",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )
