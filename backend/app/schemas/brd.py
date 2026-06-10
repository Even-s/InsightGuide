"""BRD (Business Requirements Document) schemas."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.models.brd import BRDStatus, RequirementType, RequirementPriority


# ============================================================================
# Requirement Schemas
# ============================================================================

class RequirementBase(BaseModel):
    """Base requirement schema."""
    title: str
    description: str
    type: RequirementType
    priority: RequirementPriority = RequirementPriority.SHOULD_HAVE
    user_story: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    rationale: Optional[str] = None
    dependencies: Optional[List[str]] = None
    notes: Optional[str] = None


class RequirementCreate(RequirementBase):
    """Create requirement schema."""
    source_question_card_id: Optional[str] = None
    source_utterance_ids: Optional[List[str]] = None
    confidence: Optional[float] = None


class RequirementUpdate(BaseModel):
    """Update requirement schema."""
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[RequirementType] = None
    priority: Optional[RequirementPriority] = None
    user_story: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    rationale: Optional[str] = None
    dependencies: Optional[List[str]] = None
    notes: Optional[str] = None


class RequirementResponse(RequirementBase):
    """Requirement response schema."""
    id: str
    brd_draft_id: str
    source_question_card_id: Optional[str]
    source_utterance_ids: Optional[List[str]]
    confidence: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# BRD Draft Schemas
# ============================================================================

class BRDDraftBase(BaseModel):
    """Base BRD draft schema."""
    title: Optional[str] = None
    executive_summary: Optional[str] = None
    project_overview: Optional[str] = None
    business_objectives: Optional[List[str]] = None
    success_criteria: Optional[List[str]] = None
    stakeholders: Optional[List[Dict[str, str]]] = None
    assumptions: Optional[List[str]] = None
    constraints: Optional[List[str]] = None
    risks: Optional[List[Dict[str, str]]] = None


class BRDDraftCreate(BaseModel):
    """Create BRD draft schema."""
    interview_session_id: str


class BRDDraftUpdate(BRDDraftBase):
    """Update BRD draft schema."""
    pass


class BRDDraftResponse(BRDDraftBase):
    """BRD draft response schema."""
    id: str
    interview_session_id: str
    user_id: str
    status: BRDStatus
    generated_at: Optional[datetime]
    generation_duration_seconds: Optional[int]
    error_message: Optional[str]
    markdown_content: Optional[str]
    last_exported_at: Optional[datetime]
    export_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    requirements: List[RequirementResponse] = []

    class Config:
        from_attributes = True


class BRDGenerationRequest(BaseModel):
    """Request to generate BRD from interview session."""
    interview_session_id: str = Field(..., description="Interview session ID to generate BRD from")


class BRDGenerationResponse(BaseModel):
    """Response after initiating BRD generation."""
    brd_id: str
    status: BRDStatus
    message: str


class BRDExportRequest(BaseModel):
    """Request to export BRD."""
    format: str = Field(..., description="Export format: 'markdown', 'pdf', or 'docx'")


class BRDExportResponse(BaseModel):
    """Response after exporting BRD."""
    brd_id: str
    format: str
    export_url: Optional[str] = None
    download_url: Optional[str] = None
    exported_at: datetime
