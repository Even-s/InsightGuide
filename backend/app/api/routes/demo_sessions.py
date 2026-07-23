"""Ready-to-run public demo interview routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.demo_session import (
    DemoSessionCreate,
    DemoSessionResponse,
    DemoTemplateListResponse,
)
from app.services.demo_session_service import DemoTemplateNotFoundError, demo_session_service

router = APIRouter()
DEMO_USER_ID = "user_default"


@router.get("/templates", response_model=DemoTemplateListResponse)
def list_demo_templates():
    return {"templates": demo_session_service.list_templates()}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DemoSessionResponse)
def create_demo_session(data: DemoSessionCreate, db: Session = Depends(get_db)):
    try:
        return demo_session_service.create_demo_session(
            db, user_id=DEMO_USER_ID, template_id=data.templateId
        )
    except DemoTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Demo template not found") from exc
