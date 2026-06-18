"""Card Coverage Evaluation model - Phase 2 of transcript split.

Separates provisional (live) from final coverage evaluations.
"""

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime

from app.db.session import Base


class CardCoverageEvaluation(Base):
    """Card coverage evaluation record.

    Stores coverage judgments for question cards, distinguishing between:
    - live: Provisional judgments during interview (from Realtime API transcripts)
    - final: Definitive judgments after diarization (from final transcripts)

    This allows real-time UI feedback without polluting formal BRD evidence.
    """
    __tablename__ = "card_coverage_evaluations"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    card_id = Column(String, ForeignKey("question_cards.id"), nullable=False, index=True)

    basis_type = Column(String, nullable=False, index=True)
    # live: provisional judgment from live_utterances (for real-time UI)
    # final: authoritative judgment from final_utterances (for BRD/reports)

    transcript_revision_id = Column(String, ForeignKey("transcript_revisions.id"), nullable=True)
    # Only set for final evaluations; null for live

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
    #   "utterance_table": "final_utterances" | "live_utterances",
    #   "utterance_id": "utt_xxx",
    #   "quote": "受訪者說的原文片段"
    # }]

    evaluation_seq = Column(Integer, nullable=False)
    # Monotonic sequence number to prevent race conditions
    # Higher seq number = more recent evaluation

    model = Column(String, nullable=True)
    # e.g., "gpt-5.4-nano" for live, "gpt-5.4-mini" for final

    prompt_version = Column(String, nullable=True)
    # Prompt registry version used for this evaluation

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
