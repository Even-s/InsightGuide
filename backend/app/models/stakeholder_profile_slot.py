"""Many-to-many assignment between stakeholder profiles and role slots."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base


class StakeholderProfileSlot(Base):
    """A role assignment for a stakeholder profile.

    Clean-break multi-role model: people do not belong to exactly one role.
    Instead, a profile can be assigned to many stakeholder slots and one of
    those assignments may be marked as primary for display and defaults.
    """

    __tablename__ = "stakeholder_profile_slots"
    __table_args__ = (
        UniqueConstraint("profile_id", "slot_id", name="uq_stakeholder_profile_slot"),
    )

    id = Column(String, primary_key=True)
    project_id = Column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id = Column(
        String,
        ForeignKey("stakeholder_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slot_id = Column(
        String, ForeignKey("stakeholder_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_primary = Column(Boolean, nullable=False, default=False)
    fit_level = Column(String, nullable=False, default="strong")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project")
    profile = relationship("StakeholderProfile", back_populates="slot_assignments")
    slot = relationship("StakeholderSlot", back_populates="profile_assignments")
