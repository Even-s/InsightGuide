"""Realtime card coverage evaluation model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSON

from app.db.session import Base


class CardCoverageEvaluation(Base):
    """Card coverage evaluation record.

    Stores judgments made from the canonical Realtime transcript.
    """

    __tablename__ = "card_coverage_evaluations"
    __table_args__ = (
        Index(
            "ix_card_coverage_evaluations_session_card",
            "session_id",
            "card_id",
        ),
    )

    id = Column(String, primary_key=True)
    session_id = Column(
        String,
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_id = Column(
        String,
        ForeignKey("question_cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    state = Column(String, nullable=False)
    # pending | listening | probably_sufficient | sufficient

    confidence = Column(Numeric(4, 3), nullable=True)
    # 0.000 - 1.000

    covered_element_ids = Column(JSON, nullable=True, default=list)
    # List of element IDs that have been covered

    missing_element_ids = Column(JSON, nullable=True, default=list)
    # List of element IDs that are still missing

    evidence = Column(JSON, nullable=True, default=list)
    # Array of evidence objects:
    # [{
    #   "element_id": "e1",
    #   "utterance_table": "live_utterances",
    #   "utterance_id": "utt_xxx",
    #   "quote": "受訪者說的原文片段"
    # }]

    evaluation_seq = Column(Integer, nullable=False)
    # Monotonic sequence number to prevent race conditions
    # Higher seq number = more recent evaluation

    model = Column(String, nullable=True)
    # e.g., "gpt-5.4-nano"

    prompt_version = Column(String, nullable=True)
    # Prompt registry version used for this evaluation

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
