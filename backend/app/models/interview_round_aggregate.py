"""Canonical cumulative output for an interview round."""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base


class InterviewRoundAggregate(Base):
    """One rebuildable aggregate for every interview round.

    Sessions remain immutable visit records. Downstream project analysis reads
    this object instead of combining every session memo independently.
    """

    __tablename__ = "interview_round_aggregates"
    __table_args__ = (
        UniqueConstraint("round_id", name="uq_interview_round_aggregates_round_id"),
        UniqueConstraint("latest_memo_id", name="uq_interview_round_aggregates_latest_memo_id"),
    )

    id = Column(String, primary_key=True)
    round_id = Column(
        String,
        ForeignKey("interview_rounds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    latest_memo_id = Column(
        String,
        ForeignKey("interview_insight_memos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_session_ids = Column(JSON, nullable=False, default=list)
    coverage_snapshot = Column(JSON, nullable=False, default=dict)
    evidence_snapshot = Column(JSON, nullable=False, default=list)
    status = Column(String, nullable=False, default="stale", index=True)
    version = Column(Integer, nullable=False, default=0)
    generated_at = Column(DateTime, nullable=True)
    invalidated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    interview_round = relationship("InterviewRound", back_populates="aggregate")
    latest_memo = relationship("InterviewInsightMemo", foreign_keys=[latest_memo_id])
