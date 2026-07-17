"""Stakeholder Profile model."""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class StakeholderProfile(Base):
    """StakeholderProfile model - a specific person to interview.

    A profile represents a real person. Role membership is many-to-many via
    StakeholderProfileSlot; profiles can exist independently with no role.
    """

    __tablename__ = "stakeholder_profiles"

    id = Column(String, primary_key=True)
    project_id = Column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    role_title = Column(String, nullable=True)
    department = Column(String, nullable=True)
    stakeholder_type = Column(String, nullable=False)
    expertise_tags = Column(JSON, nullable=False, default=[])
    knowledge_boundaries = Column(JSON, nullable=False, default=[])
    decision_power = Column(String, nullable=True)
    status = Column(String, nullable=False, default="scheduled")
    interview_count = Column(Integer, nullable=False, default=0)
    last_interviewed_at = Column(DateTime, nullable=True)
    recommended_by_memo_id = Column(String, nullable=True)
    recommended_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="stakeholder_profiles")
    slot_assignments = relationship(
        "StakeholderProfileSlot",
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    interview_sessions = relationship(
        "InterviewSession",
        back_populates="stakeholder_profile",
        foreign_keys="[InterviewSession.stakeholder_profile_id]",
    )
    interview_series = relationship(
        "InterviewSeries", back_populates="stakeholder_profile", cascade="all, delete-orphan"
    )
