"""User model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    prep_sessions = relationship("PrepSession", back_populates="user", cascade="all, delete-orphan")
    interview_sessions = relationship(
        "InterviewSession", back_populates="user", cascade="all, delete-orphan"
    )
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
