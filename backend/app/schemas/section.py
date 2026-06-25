"""Section Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SectionResponse(BaseModel):
    """Schema for section response."""

    id: str
    document_id: str
    section_number: int
    title: Optional[str] = None
    extracted_text: Optional[str] = None
    ai_summary: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SectionWithQuestionCards(BaseModel):
    """Schema for section with question cards."""

    id: str
    document_id: str
    section_number: int
    title: Optional[str] = None
    extracted_text: Optional[str] = None
    ai_summary: Optional[str] = None
    question_cards_count: int = 0

    class Config:
        from_attributes = True
