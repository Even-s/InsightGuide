"""Interview Brief model."""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class InterviewBrief(Base):
    """InterviewBrief model - role-based interview plan generated before a session.

    Contains recommended topics, excluded topics, suggested questions,
    and follow-ups from prior interviews. Generated based on stakeholder
    profile + project scope + evidence gaps.
    """

    __tablename__ = "interview_briefs"

    id = Column(String, primary_key=True)
    session_id = Column(
        String, ForeignKey("interview_sessions.id"), nullable=False, unique=True, index=True
    )
    stakeholder_profile_id = Column(String, ForeignKey("stakeholder_profiles.id"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)

    interview_objective = Column(Text, nullable=False)

    recommended_topics = Column(JSON, nullable=False, default=[])
    excluded_topics = Column(JSON, nullable=False, default=[])
    suggested_questions = Column(JSON, nullable=False, default=[])
    follow_up_from_prior_interviews = Column(JSON, nullable=False, default=[])

    applicable_card_ids = Column(JSON, nullable=False, default=[])
    not_applicable_cards = Column(JSON, nullable=False, default=[])

    time_estimate_minutes = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    session = relationship("InterviewSession", back_populates="interview_brief")
    stakeholder_profile = relationship("StakeholderProfile")
    project = relationship("Project")
