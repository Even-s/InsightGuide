"""Project model."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Project(Base):
    """Project model - top-level container for a BRD initiative.

    Groups multiple stakeholders, interviews, and documents under
    a single business objective with defined scope.
    """

    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    brd_scope = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="active", index=True)
    mode = Column(String, nullable=False, default="formal", index=True)
    is_ephemeral = Column(Boolean, nullable=False, default=False, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    template_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="projects")
    stakeholder_slots = relationship(
        "StakeholderSlot", back_populates="project", cascade="all, delete-orphan"
    )
    stakeholder_profiles = relationship(
        "StakeholderProfile", back_populates="project", cascade="all, delete-orphan"
    )
    documents = relationship(
        "Document",
        back_populates="project",
        foreign_keys="[Document.project_id]",
        cascade="all, delete-orphan",
    )
    interview_sessions = relationship(
        "InterviewSession",
        back_populates="project",
        foreign_keys="[InterviewSession.project_id]",
        cascade="all, delete-orphan",
    )
    interview_series = relationship(
        "InterviewSeries", back_populates="project", cascade="all, delete-orphan"
    )
    insight_memos = relationship(
        "InterviewInsightMemo", back_populates="project", cascade="all, delete-orphan"
    )
    evidence_matrix = relationship(
        "RequirementEvidenceMatrix",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
