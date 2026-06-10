"""Prep Session models."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class PrepSession(Base):
    """PrepSession model - represents a preparation session for a requirements document."""

    __tablename__ = "prep_sessions"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, unique=True, index=True)  # One prep session per document
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=True)  # Optional user-defined title
    status = Column(String, nullable=False, default="preparing", index=True)  # preparing, ready, archived
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="prep_sessions")
    user = relationship("User", back_populates="prep_sessions")
    interview_sessions = relationship(
        "InterviewSession",
        back_populates="prep_session",
        cascade="all, delete-orphan"
    )
