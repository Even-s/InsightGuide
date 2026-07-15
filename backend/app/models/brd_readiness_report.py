"""BRD Readiness Report model."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class BRDReadinessReport(Base):
    """BRDReadinessReport - gatekeeper before BRD generation.

    Evaluates whether enough evidence has been gathered across
    stakeholder interviews to produce a reliable BRD.
    """

    __tablename__ = "brd_readiness_reports"

    id = Column(String, primary_key=True)
    project_id = Column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    is_ready = Column(Boolean, nullable=False, default=False)
    readiness_score = Column(Float, nullable=True)
    generation_mode = Column(String, nullable=True)
    recommendation = Column(Text, nullable=True)

    ready_sections = Column(JSON, nullable=False, default=[])
    insufficient_sections = Column(JSON, nullable=False, default=[])
    unresolved_conflicts = Column(JSON, nullable=False, default=[])
    suggested_next_interviews = Column(JSON, nullable=False, default=[])

    stakeholder_coverage = Column(JSON, nullable=True)

    total_memos = Column(Integer, nullable=False, default=0)
    total_stakeholders_interviewed = Column(Integer, nullable=False, default=0)
    total_evidence_entries = Column(Integer, nullable=False, default=0)
    validated_requirements = Column(Integer, nullable=False, default=0)

    markdown_content = Column(Text, nullable=True)

    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    project = relationship("Project")
