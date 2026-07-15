"""Interview series model for grouping multiple rounds with one stakeholder and topic."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base


class InterviewSeries(Base):
    """A durable topic thread for repeated interviews with one stakeholder."""

    __tablename__ = "interview_series"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "stakeholder_profile_id",
            "topic_key",
            name="uq_interview_series_project_profile_topic",
        ),
    )

    id = Column(String, primary_key=True)
    project_id = Column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stakeholder_profile_id = Column(
        String,
        ForeignKey("stakeholder_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String, nullable=False)
    topic_key = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="interview_series")
    stakeholder_profile = relationship("StakeholderProfile", back_populates="interview_series")
    rounds = relationship(
        "InterviewRound",
        back_populates="series",
        cascade="all, delete-orphan",
        order_by="InterviewRound.round_number",
    )
