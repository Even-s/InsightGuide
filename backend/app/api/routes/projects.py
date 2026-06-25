"""Project, Stakeholder Plan, and Stakeholder Profile routes."""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.project import (
    ProjectCreate,
    ProjectDashboardResponse,
    ProjectListResponse,
    ProjectSchema,
    ProjectUpdate,
    StakeholderPlanResponse,
    StakeholderProfileCreate,
    StakeholderProfileSchema,
    StakeholderProfileUpdate,
    StakeholderSlotCreate,
    StakeholderSlotSchema,
    StakeholderSlotUpdate,
)
from app.services.project_service import project_service
from app.services.stakeholder_plan_service import stakeholder_plan_service

logger = logging.getLogger(__name__)

router = APIRouter()

DEMO_USER_ID = "user_default"


def _project_to_schema(project) -> ProjectSchema:
    return ProjectSchema(
        id=project.id,
        userId=project.user_id,
        title=project.title,
        description=project.description,
        brdScope=project.brd_scope,
        status=project.status,
        createdAt=project.created_at,
        updatedAt=project.updated_at,
    )


def _slot_to_schema(slot, db: Session) -> StakeholderSlotSchema:
    from app.models.stakeholder_profile import StakeholderProfile

    profiles = db.query(StakeholderProfile).filter(StakeholderProfile.slot_id == slot.id).all()
    interviews_done = sum(p.interview_count for p in profiles)

    return StakeholderSlotSchema(
        id=slot.id,
        projectId=slot.project_id,
        roleCategory=slot.role_category,
        roleLabel=slot.role_label,
        rationale=slot.rationale,
        expectedContributions=slot.expected_contributions or [],
        keyQuestionsToCover=slot.key_questions_to_cover or [],
        priority=slot.priority,
        minInterviews=slot.min_interviews,
        status=slot.status,
        orderIndex=slot.order_index,
        source=slot.source,
        profilesCount=len(profiles),
        interviewsDone=interviews_done,
        createdAt=slot.created_at,
        updatedAt=slot.updated_at,
    )


def _profile_to_schema(profile) -> StakeholderProfileSchema:
    return StakeholderProfileSchema(
        id=profile.id,
        projectId=profile.project_id,
        slotId=profile.slot_id,
        name=profile.name,
        roleTitle=profile.role_title,
        department=profile.department,
        stakeholderType=profile.stakeholder_type,
        expertiseTags=profile.expertise_tags or [],
        knowledgeBoundaries=profile.knowledge_boundaries or [],
        decisionPower=profile.decision_power,
        status=profile.status,
        interviewCount=profile.interview_count,
        lastInterviewedAt=profile.last_interviewed_at,
        recommendedByMemoId=profile.recommended_by_memo_id,
        recommendedReason=profile.recommended_reason,
        notes=profile.notes,
        createdAt=profile.created_at,
        updatedAt=profile.updated_at,
    )


# --- Voice Input ---


@router.post("/voice-to-project-fields")
async def voice_to_project_fields(audio: UploadFile = File(...)):
    """Transcribe audio and parse into project creation fields using GPT.

    Accepts audio file (webm, mp4, wav, etc.), transcribes with Whisper,
    then uses GPT to extract: title, description, business_domain, key_objectives.
    """
    from app.services.openai_service import openai_service

    audio_bytes = await audio.read()
    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=400, detail="Audio too short")

    # Step 1: Transcribe with Whisper
    try:
        import io

        filename = audio.filename or "audio.webm"
        transcript_response = openai_service.client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, io.BytesIO(audio_bytes)),
            language="zh",
        )
        transcript = transcript_response.text.strip()
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        raise HTTPException(status_code=500, detail="語音轉文字失敗")

    if not transcript:
        raise HTTPException(status_code=400, detail="無法辨識語音內容")

    # Step 2: GPT parse transcript into project fields
    from app.core.config import settings

    try:
        ai_result = openai_service.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是專案需求分析助手。使用者用語音描述了一個專案需求。"
                        "請從中萃取結構化資訊，填入 JSON 格式。\n"
                        "如果某欄位使用者沒有提到，設為 null。\n"
                        "只回傳 JSON，不要其他文字。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"使用者說了以下內容：\n\n「{transcript}」\n\n"
                        "請萃取為以下 JSON 格式：\n"
                        "{\n"
                        '  "title": "專案名稱（簡短）",\n'
                        '  "description": "專案描述（一兩句話）",\n'
                        '  "business_domain": "業務領域",\n'
                        '  "key_objectives": ["目標1", "目標2", ...],\n'
                        '  "out_of_scope": ["不在範圍內的事項"]\n'
                        "}"
                    ),
                },
            ],
            model=settings.SEMANTIC_UNDERSTANDING_MODEL,
            temperature=0.2,
            max_tokens=500,
            response_format={"type": "json_object"},
            purpose="project_voice_parse",
        )

        if isinstance(ai_result, str):
            content = ai_result.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(content)
        else:
            parsed = ai_result
    except Exception as e:
        logger.error(f"GPT parsing failed: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"AI 分析失敗：{type(e).__name__}: {e}",
        )

    return {
        "transcript": transcript,
        "parsed": {
            "title": parsed.get("title"),
            "description": parsed.get("description"),
            "business_domain": parsed.get("business_domain"),
            "key_objectives": parsed.get("key_objectives") or [],
            "out_of_scope": parsed.get("out_of_scope") or [],
        },
    }


# --- Project CRUD ---


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project and auto-generate stakeholder plan."""
    project = project_service.create_project(
        db,
        user_id=DEMO_USER_ID,
        title=data.title,
        description=data.description,
    )

    return _project_to_schema(project)


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    """List all projects for the current user."""
    projects = project_service.list_projects(db, DEMO_USER_ID)
    return ProjectListResponse(
        projects=[_project_to_schema(p) for p in projects],
        total=len(projects),
    )


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    """Get a project by ID."""
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_schema(project)


@router.get("/{project_id}/dashboard")
def get_project_dashboard(project_id: str, db: Session = Depends(get_db)):
    """Get project dashboard overview."""
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    dashboard = project_service.get_dashboard(db, project_id)
    return ProjectDashboardResponse(
        project=_project_to_schema(dashboard["project"]),
        stakeholderPlan=dashboard["stakeholder_plan"],
        interviewProgress=dashboard["interview_progress"],
        nextAction=dashboard["next_action"],
    )


@router.put("/{project_id}")
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db)):
    """Update a project."""
    update_data = data.model_dump(exclude_none=True)
    project = project_service.update_project(db, project_id, update_data)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_schema(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete a project."""
    if not project_service.delete_project(db, project_id):
        raise HTTPException(status_code=404, detail="Project not found")


# --- Stakeholder Plan (Slots) ---


@router.get("/{project_id}/stakeholder-plan")
def get_stakeholder_plan(project_id: str, db: Session = Depends(get_db)):
    """Get the full stakeholder plan (slots + profiles + summary)."""
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.models.stakeholder_profile import StakeholderProfile
    from app.models.stakeholder_slot import StakeholderSlot

    slots = (
        db.query(StakeholderSlot)
        .filter(StakeholderSlot.project_id == project_id)
        .order_by(StakeholderSlot.order_index)
        .all()
    )

    profiles = (
        db.query(StakeholderProfile)
        .filter(StakeholderProfile.project_id == project_id)
        .order_by(StakeholderProfile.created_at)
        .all()
    )

    summary = stakeholder_plan_service.get_plan_status(db, project_id)

    return StakeholderPlanResponse(
        slots=[_slot_to_schema(s, db) for s in slots],
        profiles=[_profile_to_schema(p) for p in profiles],
        summary=summary,
    )


@router.post("/{project_id}/stakeholder-plan/regenerate")
def regenerate_stakeholder_plan(project_id: str, db: Session = Depends(get_db)):
    """Regenerate stakeholder plan from brd_scope (replaces AI-suggested slots)."""
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.models.stakeholder_slot import StakeholderSlot

    # Only delete AI-suggested slots, keep user-created ones
    db.query(StakeholderSlot).filter(
        StakeholderSlot.project_id == project_id,
        StakeholderSlot.source == "ai_suggested",
    ).delete()
    db.commit()

    slots = stakeholder_plan_service.generate_initial_plan(db, project_id)
    return {"slots": [_slot_to_schema(s, db) for s in slots]}


@router.post("/{project_id}/stakeholder-slots", status_code=status.HTTP_201_CREATED)
def create_stakeholder_slot(
    project_id: str, data: StakeholderSlotCreate, db: Session = Depends(get_db)
):
    """Manually add a stakeholder slot."""
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    slot = stakeholder_plan_service.create_slot(db, project_id, data.model_dump())
    return _slot_to_schema(slot, db)


@router.put("/stakeholder-slots/reorder")
def reorder_stakeholder_slots(body: dict, db: Session = Depends(get_db)):
    """Reorder stakeholder slots. Body: { "slot_ids": ["id1", "id2", ...] }"""
    slot_ids = body.get("slot_ids", [])
    if not slot_ids:
        raise HTTPException(status_code=400, detail="slot_ids is required")
    stakeholder_plan_service.reorder_slots(db, slot_ids)
    return {"ok": True}


@router.put("/stakeholder-slots/{slot_id}")
def update_stakeholder_slot(
    slot_id: str, data: StakeholderSlotUpdate, db: Session = Depends(get_db)
):
    """Update a stakeholder slot."""
    update_data = data.model_dump(exclude_none=True)
    slot = stakeholder_plan_service.update_slot(db, slot_id, update_data)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    return _slot_to_schema(slot, db)


@router.put("/stakeholder-slots/{slot_id}/skip")
def skip_stakeholder_slot(slot_id: str, db: Session = Depends(get_db)):
    """Mark a slot as skipped (can't find this role)."""
    slot = stakeholder_plan_service.skip_slot(db, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    return _slot_to_schema(slot, db)


@router.put("/stakeholder-slots/{slot_id}/unskip")
def unskip_stakeholder_slot(slot_id: str, db: Session = Depends(get_db)):
    """Restore a skipped slot back to unassigned."""
    slot = stakeholder_plan_service.unskip_slot(db, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    return _slot_to_schema(slot, db)


@router.delete("/stakeholder-slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stakeholder_slot(slot_id: str, db: Session = Depends(get_db)):
    """Delete a stakeholder slot."""
    if not stakeholder_plan_service.delete_slot(db, slot_id):
        raise HTTPException(status_code=404, detail="Slot not found")


# --- Stakeholder Profiles ---


@router.post("/{project_id}/stakeholders", status_code=status.HTTP_201_CREATED)
def create_stakeholder(
    project_id: str, data: StakeholderProfileCreate, db: Session = Depends(get_db)
):
    """Add a stakeholder profile to the project."""
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    profile = stakeholder_plan_service.create_profile(db, project_id, data.model_dump())
    return _profile_to_schema(profile)


@router.get("/{project_id}/stakeholders")
def list_stakeholders(project_id: str, db: Session = Depends(get_db)):
    """List all stakeholder profiles for a project."""
    from app.models.stakeholder_profile import StakeholderProfile

    profiles = (
        db.query(StakeholderProfile)
        .filter(StakeholderProfile.project_id == project_id)
        .order_by(StakeholderProfile.created_at)
        .all()
    )
    return [_profile_to_schema(p) for p in profiles]


@router.put("/stakeholders/{profile_id}")
def update_stakeholder(
    profile_id: str, data: StakeholderProfileUpdate, db: Session = Depends(get_db)
):
    """Update a stakeholder profile."""
    update_data = data.model_dump(exclude_none=True)
    profile = stakeholder_plan_service.update_profile(db, profile_id, update_data)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _profile_to_schema(profile)


@router.put("/stakeholders/{profile_id}/cancel")
def cancel_stakeholder(profile_id: str, db: Session = Depends(get_db)):
    """Mark a stakeholder as unavailable."""
    profile = stakeholder_plan_service.cancel_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _profile_to_schema(profile)


@router.delete("/stakeholders/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stakeholder(profile_id: str, db: Session = Depends(get_db)):
    """Delete a stakeholder profile."""
    if not stakeholder_plan_service.delete_profile(db, profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")


# --- BRD Readiness ---


@router.post("/{project_id}/readiness-check")
def generate_readiness_report(project_id: str, db: Session = Depends(get_db)):
    """Generate a BRD Readiness Report for the project."""
    from app.services.brd_readiness_service import brd_readiness_service

    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        report = brd_readiness_service.generate_report(db, project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _readiness_to_response(report)


@router.get("/{project_id}/readiness-report")
def get_readiness_report(project_id: str, db: Session = Depends(get_db)):
    """Get the latest BRD Readiness Report."""
    from app.services.brd_readiness_service import brd_readiness_service

    report = brd_readiness_service.get_latest_report(db, project_id)
    if not report:
        raise HTTPException(
            status_code=404, detail="No readiness report found. Run a readiness check first."
        )

    return _readiness_to_response(report)


@router.post("/{project_id}/generate-brd")
def generate_project_brd(project_id: str, db: Session = Depends(get_db)):
    """Generate BRD for a project (runs readiness check first).

    Returns the BRD if ready, or the readiness report with suggestions if not.
    """
    from app.services.brd_generation_service import brd_generation_service
    from app.services.brd_readiness_service import brd_readiness_service

    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    check = brd_readiness_service.can_generate_brd(db, project_id)

    if not check["can_generate"]:
        report = brd_readiness_service.generate_report(db, project_id)
        return {
            "status": "not_ready",
            "readinessReport": _readiness_to_response(report),
            "message": check["reason"],
        }

    # Generate project-level BRD from evidence matrix
    try:
        brd_result = brd_generation_service.generate_project_brd(db, project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BRD generation failed: {e}")

    report = brd_readiness_service.get_latest_report(db, project_id)
    return {
        "status": check["mode"],
        "readinessReport": _readiness_to_response(report) if report else None,
        "message": check["reason"],
        "brd": brd_result,
    }


def _readiness_to_response(report) -> dict:
    """Convert BRDReadinessReport to API response."""
    return {
        "id": report.id,
        "projectId": report.project_id,
        "isReady": report.is_ready,
        "readinessScore": report.readiness_score,
        "generationMode": report.generation_mode,
        "recommendation": report.recommendation,
        "readySections": report.ready_sections or [],
        "insufficientSections": report.insufficient_sections or [],
        "unresolvedConflicts": report.unresolved_conflicts or [],
        "suggestedNextInterviews": report.suggested_next_interviews or [],
        "stakeholderCoverage": report.stakeholder_coverage,
        "totalMemos": report.total_memos,
        "totalStakeholdersInterviewed": report.total_stakeholders_interviewed,
        "totalEvidenceEntries": report.total_evidence_entries,
        "validatedRequirements": report.validated_requirements,
        "markdownContent": report.markdown_content,
        "generatedAt": report.generated_at.isoformat() if report.generated_at else None,
    }


# --- Stakeholder Interview Guide Generation ---


class InterviewGuideOptions(BaseModel):
    """Options for interview guide generation."""

    duration_minutes: int = 30
    interview_purpose: Optional[str] = None
    focus_topics: Optional[str] = None
    exclude_topics: Optional[str] = None
    interview_style: Optional[str] = None  # exploratory / structured / validation
    target_card_count: Optional[int] = None
    must_cover_topics: Optional[List[str]] = None
    reference_questions: Optional[List[str]] = None

    class Config:
        extra = "ignore"


@router.post("/{project_id}/stakeholders/{profile_id}/generate-interview-guide")
def generate_interview_guide(
    project_id: str,
    profile_id: str,
    options: Optional[InterviewGuideOptions] = None,
    db: Session = Depends(get_db),
):
    """Generate interview guide (cards) for a specific stakeholder.

    Accepts optional generation options (duration, purpose, focus, etc.).
    """
    from app.services.stakeholder_card_generator import stakeholder_card_generator

    generation_options = None
    if options:
        generation_options = options.model_dump(exclude_none=True)

    try:
        result = stakeholder_card_generator.generate_cards_for_stakeholder(
            db, project_id, profile_id, options=generation_options
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate interview guide: {e}")
        raise HTTPException(status_code=500, detail=f"Interview guide generation failed: {e}")


@router.get("/{project_id}/stakeholders/{profile_id}/interview-guide")
def get_interview_guide(project_id: str, profile_id: str, db: Session = Depends(get_db)):
    """Get the interview guide status for a stakeholder.

    Returns the document, prep session, themes, and card count if generated.
    Returns 404 if not yet generated.
    """
    from app.services.stakeholder_card_generator import stakeholder_card_generator

    result = stakeholder_card_generator.get_interview_guide_status(db, project_id, profile_id)

    if not result:
        raise HTTPException(
            status_code=404, detail="Interview guide not yet generated for this stakeholder"
        )

    return result
