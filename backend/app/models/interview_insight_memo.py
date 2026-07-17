"""Interview Insight Memo model."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class InterviewInsightMemo(Base):
    """InterviewInsightMemo model - structured insight document from a single interview.

    Generated from role-neutral Realtime transcript segments. Contains
    question-level summaries, pain points, requirement candidates, constraints,
    process descriptions, and unresolved questions. Each item is tagged with
    source distinction (explicit/inferred/unverified).
    """

    __tablename__ = "interview_insight_memos"
    __table_args__ = (
        UniqueConstraint("session_id"),
        Index("ix_insight_memos_session_id", "session_id"),
        Index("ix_insight_memos_project_id", "project_id"),
        Index("ix_insight_memos_stakeholder_id", "stakeholder_profile_id"),
    )

    id = Column(String, primary_key=True)
    session_id = Column(
        String, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    project_id = Column(String, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    stakeholder_profile_id = Column(
        String,
        ForeignKey("stakeholder_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    interview_series_id = Column(
        String, ForeignKey("interview_series.id", ondelete="SET NULL"), nullable=True, index=True
    )
    interview_round_id = Column(
        String, ForeignKey("interview_rounds.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Section 1: Basic info
    interview_date = Column(DateTime, nullable=True)
    interview_duration_minutes = Column(Integer, nullable=True)
    topics_covered = Column(JSON, nullable=False, default=[])
    stakeholder_summary = Column(JSON, nullable=True)

    # Section 2: question-card summaries
    question_summaries = Column(JSON, nullable=False, default=[])

    # Section 3: Pain points
    pain_points = Column(JSON, nullable=False, default=[])

    # Section 4: Requirement candidates
    requirement_candidates = Column(JSON, nullable=False, default=[])

    # Section 5: Constraints and assumptions
    constraints_and_assumptions = Column(JSON, nullable=False, default=[])

    # Section 6: Process descriptions
    process_descriptions = Column(JSON, nullable=False, default=[])

    # Section 7: Unresolved questions
    unresolved_questions = Column(JSON, nullable=False, default=[])

    # Section 8: Next interview suggestions
    next_interview_suggestions = Column(JSON, nullable=False, default=[])

    # Metadata
    source_distinction = Column(JSON, nullable=True)
    markdown_content = Column(Text, nullable=True)

    status = Column(String, nullable=False, default="generating")
    generated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    session = relationship("InterviewSession", back_populates="insight_memo")
    project = relationship("Project", back_populates="insight_memos")
    stakeholder_profile = relationship("StakeholderProfile")
    interview_round = relationship("InterviewRound", back_populates="insight_memos")
