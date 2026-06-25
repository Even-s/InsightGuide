"""Project and Stakeholder Pydantic schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# --- Project ---


class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    brd_scope: Optional[Dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    brd_scope: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class ProjectSchema(BaseModel):
    id: str
    userId: str
    title: str
    description: Optional[str] = None
    brdScope: Optional[Dict[str, Any]] = None
    status: str
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    projects: List[ProjectSchema]
    total: int


# --- Stakeholder Slot ---


class StakeholderSlotCreate(BaseModel):
    role_category: str
    role_label: str
    rationale: Optional[str] = None
    expected_contributions: List[str] = Field(default_factory=list)
    key_questions_to_cover: List[str] = Field(default_factory=list)
    priority: str = "required"
    min_interviews: int = 1


class StakeholderSlotUpdate(BaseModel):
    role_category: Optional[str] = None
    role_label: Optional[str] = None
    rationale: Optional[str] = None
    expected_contributions: Optional[List[str]] = None
    key_questions_to_cover: Optional[List[str]] = None
    priority: Optional[str] = None
    min_interviews: Optional[int] = None
    status: Optional[str] = None
    order_index: Optional[int] = None


class StakeholderSlotSchema(BaseModel):
    id: str
    projectId: str
    roleCategory: str
    roleLabel: str
    rationale: Optional[str] = None
    expectedContributions: List[str] = Field(default_factory=list)
    keyQuestionsToCover: List[str] = Field(default_factory=list)
    priority: str
    minInterviews: int
    status: str
    orderIndex: int
    source: str
    profilesCount: int = 0
    interviewsDone: int = 0
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


# --- Stakeholder Profile ---


class StakeholderProfileCreate(BaseModel):
    slot_id: Optional[str] = None
    name: str
    role_title: Optional[str] = None
    department: Optional[str] = None
    stakeholder_type: str
    expertise_tags: List[str] = Field(default_factory=list)
    knowledge_boundaries: List[str] = Field(default_factory=list)
    decision_power: Optional[str] = None
    notes: Optional[str] = None


class StakeholderProfileUpdate(BaseModel):
    slot_id: Optional[str] = None
    name: Optional[str] = None
    role_title: Optional[str] = None
    department: Optional[str] = None
    stakeholder_type: Optional[str] = None
    expertise_tags: Optional[List[str]] = None
    knowledge_boundaries: Optional[List[str]] = None
    decision_power: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class StakeholderProfileSchema(BaseModel):
    id: str
    projectId: str
    slotId: Optional[str] = None
    name: str
    roleTitle: Optional[str] = None
    department: Optional[str] = None
    stakeholderType: str
    expertiseTags: List[str] = Field(default_factory=list)
    knowledgeBoundaries: List[str] = Field(default_factory=list)
    decisionPower: Optional[str] = None
    status: str
    interviewCount: int = 0
    lastInterviewedAt: Optional[datetime] = None
    recommendedByMemoId: Optional[str] = None
    recommendedReason: Optional[str] = None
    notes: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


# --- Stakeholder Plan (composite response) ---


class StakeholderPlanResponse(BaseModel):
    slots: List[StakeholderSlotSchema]
    profiles: List[StakeholderProfileSchema]
    summary: Dict[str, Any] = Field(default_factory=dict)


# --- Project Dashboard ---


class ProjectDashboardResponse(BaseModel):
    project: ProjectSchema
    stakeholderPlan: Dict[str, Any] = Field(default_factory=dict)
    interviewProgress: Dict[str, Any] = Field(default_factory=dict)
    nextAction: Optional[Dict[str, Any]] = None
