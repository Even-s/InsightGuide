"""Document-related Pydantic schemas."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    """Schema for creating a new document."""

    title: str = Field(..., min_length=1, max_length=255, description="Document title")


class DocumentResponse(BaseModel):
    """Schema for document response."""

    id: str
    user_id: str
    project_id: Optional[str] = None
    title: str
    source_file_url: str
    file_type: str  # pdf, docx, doc, md, txt
    status: str
    created_at: datetime
    updated_at: datetime
    cost_usd: float = 0.0
    ai_usage: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class DocumentStatus(BaseModel):
    """Schema for document status."""

    id: str
    status: str
    message: Optional[str] = None
    cost_usd: float = 0.0
    ai_usage: Dict[str, Any] = Field(default_factory=dict)


class DocumentAnalysisResponse(BaseModel):
    """Schema for document analysis results."""

    document_id: str
    status: str
    slides: List[dict] = Field(default_factory=list)
    topic_cards_count: int = 0
    created_at: datetime
    updated_at: datetime
    cost_usd: float = 0.0
    ai_usage: Dict[str, Any] = Field(default_factory=dict)
