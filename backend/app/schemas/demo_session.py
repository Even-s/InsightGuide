"""Public demo interview template and session schemas."""

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict


class DemoTemplateSchema(BaseModel):
    id: str
    title: str
    description: str
    estimatedMinutes: int
    themeCount: int
    questionCount: int


class DemoTemplateListResponse(BaseModel):
    templates: List[DemoTemplateSchema]


class DemoSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    templateId: str


class DemoSessionResponse(BaseModel):
    templateId: str
    projectId: str
    stakeholderProfileId: str
    prepSessionId: str
    documentId: str
    sessionId: str
    expiresAt: datetime
    interviewPath: str
