"""Requirement Evidence Matrix models."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base


class RequirementEvidenceMatrix(Base):
    """RequirementEvidenceMatrix - derived evidence matrix refresh metadata.

    Requirement rows are derived from RoundAggregate at read time. This model
    stores only refresh metadata and markdown output so it cannot become a
    second source of truth.
    """

    __tablename__ = "requirement_evidence_matrices"
    __table_args__ = (
        UniqueConstraint("project_id"),
        Index("ix_evidence_matrices_project_id", "project_id"),
    )

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    status = Column(String, nullable=False, default="draft")
    last_updated_at = Column(DateTime, nullable=True)
    memo_count = Column(Integer, nullable=False, default=0)
    last_memo_id = Column(String, nullable=True)
    markdown_content = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="evidence_matrix")
