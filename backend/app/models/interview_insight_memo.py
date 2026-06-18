"""Interview Insight Memo model."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Integer, Float
from sqlalchemy.orm import relationship

from app.db.session import Base


class InterviewInsightMemo(Base):
    """InterviewInsightMemo model - structured insight document from a single interview.

    Generated after Q/A reconstruction. Contains pain points, requirement
    candidates, constraints, process descriptions, and unresolved questions.
    Each item is tagged with source distinction (explicit/inferred/unverified).
    """

    __tablename__ = "interview_insight_memos"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, unique=True, index=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True, index=True)
    stakeholder_profile_id = Column(String, ForeignKey("stakeholder_profiles.id"), nullable=True, index=True)

    # Section 1: Basic info
    interview_date = Column(DateTime, nullable=True)
    interview_duration_minutes = Column(Integer, nullable=True)
    topics_covered = Column(JSON, nullable=False, default=[])
    stakeholder_summary = Column(JSON, nullable=True)

    # Section 2: Q/A summaries
    qa_summaries = Column(JSON, nullable=False, default=[])

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
