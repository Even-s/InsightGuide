"""Requirement Evidence Matrix models."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class RequirementEvidenceMatrix(Base):
    """RequirementEvidenceMatrix - cross-interview requirement aggregation.

    One per project. Consolidates requirement candidates from all
    Insight Memos, deduplicates, detects conflicts, and tracks
    validation status across stakeholder roles.
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

    # Relationships
    project = relationship("Project", back_populates="evidence_matrix")
    entries = relationship(
        "EvidenceMatrixEntry", back_populates="matrix", cascade="all, delete-orphan"
    )


class EvidenceMatrixEntry(Base):
    """EvidenceMatrixEntry - a single candidate requirement row in the matrix."""

    __tablename__ = "evidence_matrix_entries"

    id = Column(String, primary_key=True)
    matrix_id = Column(
        String,
        ForeignKey("requirement_evidence_matrices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    requirement_candidate = Column(Text, nullable=False)
    category = Column(String, nullable=True)

    source_roles = Column(JSON, nullable=False, default=[])
    source_memo_ids = Column(JSON, nullable=False, default=[])
    supporting_evidence = Column(JSON, nullable=False, default=[])
    conflicts = Column(JSON, nullable=False, default=[])

    validation_status = Column(String, nullable=False, default="candidate")
    missing_validation_from = Column(JSON, nullable=False, default=[])

    mention_count = Column(Integer, nullable=False, default=1)
    stakeholder_agreement_level = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    matrix = relationship("RequirementEvidenceMatrix", back_populates="entries")
