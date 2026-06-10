"""Prep session Pydantic schemas."""

from typing import Literal, Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class PrepSessionSchema(BaseModel):
    """Prep session schema."""
    id: str
    documentId: str
    userId: str
    title: Optional[str] = None
    status: Literal["preparing", "ready", "archived"]
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)


class PrepSessionCreate(BaseModel):
    """Schema for creating a prep session."""
    documentId: str
    title: Optional[str] = None


class PrepSessionUpdate(BaseModel):
    """Schema for updating a prep session."""
    title: Optional[str] = None
    status: Optional[Literal["preparing", "ready", "archived"]] = None


class PrepSessionWithDocument(BaseModel):
    """Prep session with document information."""
    id: str
    documentId: str
    documentTitle: str
    userId: str
    title: Optional[str] = None
    status: Literal["preparing", "ready", "archived"]
    createdAt: datetime
    updatedAt: datetime
    interviewSessionsCount: int = 0
    documentCostUsd: float = 0.0
    documentAiUsage: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class PrepSessionListResponse(BaseModel):
    """Response schema for prep session list with pagination."""
    prepSessions: List[PrepSessionWithDocument]
    total: int
    limit: int
    offset: int
