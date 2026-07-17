"""Session lifecycle routes: CRUD and state transitions."""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.routes.interview_helpers import convert_session_to_schema
from app.db.session import get_db
from app.schemas.interview import (
    InterviewSessionCreate,
    InterviewSessionListResponse,
    InterviewSessionSchema,
    InterviewSessionUpdate,
)
from app.services.interview_service import interview_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=InterviewSessionListResponse)
async def list_interview_sessions(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    project_id: Optional[str] = Query(None, alias="projectId"),
    document_id: Optional[str] = Query(None, alias="documentId"),
    stakeholder_profile_id: Optional[str] = Query(None, alias="stakeholderProfileId"),
    db: Session = Depends(get_db),
):
    """
    List interview sessions with pagination.

    Query parameters:
    - limit: Number of sessions to return (1-1000, default 50)
    - offset: Number of sessions to skip (for pagination)
    - projectId: Optional filter by project
    - documentId: Optional filter by document
    """
    logger.info(
        f"Listing interview sessions: limit={limit}, offset={offset}, "
        f"project_id={project_id}, document_id={document_id}"
    )

    # For MVP, use default user
    user_id = "user_default"

    result = interview_service.list_sessions(
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset,
        project_id=project_id,
        document_id=document_id,
        stakeholder_profile_id=stakeholder_profile_id,
    )

    return result


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=InterviewSessionSchema)
async def create_interview_session(
    session_data: InterviewSessionCreate, db: Session = Depends(get_db)
):
    """
    Create a new interview session under a prep session.

    This initializes an interview session and creates
    initial card states for all question cards.

    Note: This requires prepSessionId in the request body.
    Alternatively, use POST /api/prep-sessions/{prep_session_id}/interview-sessions
    """
    logger.info(f"Creating interview session for prep session {session_data.prepSessionId}")

    # For MVP, use default user
    user_id = "user_default"

    session = interview_service.create_session(db, user_id, session_data)
    return convert_session_to_schema(session, db)


@router.get("/{session_id}", response_model=InterviewSessionSchema)
async def get_interview_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Get interview session by ID. Does not block on rubric prewarming."""
    logger.info(f"Retrieving interview session {session_id}")
    session = interview_service.get_session(db, session_id)
    return convert_session_to_schema(session, db)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview_session(session_id: str, db: Session = Depends(get_db)):
    """
    Delete an interview session and all related data.

    This will cascade delete:
    - All interview card states
    - All utterances
    """
    logger.info(f"Deleting interview session {session_id}")
    interview_service.delete_session(db, session_id)

    return None


@router.patch("/{session_id}", response_model=InterviewSessionSchema)
async def update_interview_session(
    session_id: str, update_data: InterviewSessionUpdate, db: Session = Depends(get_db)
):
    """Update interview session status or current theme."""
    logger.info(f"Updating interview session {session_id}")
    session = interview_service.update_session(db, session_id, update_data)
    return convert_session_to_schema(session, db)


@router.patch("/{session_id}/current-theme", response_model=InterviewSessionSchema)
async def update_current_theme(
    session_id: str, theme_id: str = Body(..., embed=True), db: Session = Depends(get_db)
):
    """
    Update current interview theme in interview session.

    This triggers theme transition logic and may update card states
    (e.g., mark pending "must" cards as at_risk).
    """
    logger.info(f"Updating current theme for session {session_id} to {theme_id}")

    update_data = InterviewSessionUpdate(currentThemeId=theme_id)
    session = interview_service.update_session(db, session_id, update_data)

    return convert_session_to_schema(session, db)


@router.post("/{session_id}/start", response_model=InterviewSessionSchema)
async def start_interview_session(session_id: str, db: Session = Depends(get_db)):
    """Start an interview session."""
    logger.info(f"Starting interview session {session_id}")
    update_data = InterviewSessionUpdate(status="interviewing")
    session = interview_service.update_session(db, session_id, update_data)
    return convert_session_to_schema(session, db)


@router.post("/{session_id}/pause", response_model=InterviewSessionSchema)
async def pause_interview_session(session_id: str, db: Session = Depends(get_db)):
    """Pause an interview session."""
    logger.info(f"Pausing interview session {session_id}")
    update_data = InterviewSessionUpdate(status="paused")
    session = interview_service.update_session(db, session_id, update_data)
    return convert_session_to_schema(session, db)


@router.post("/{session_id}/resume", response_model=InterviewSessionSchema)
async def resume_interview_session(session_id: str, db: Session = Depends(get_db)):
    """Resume a paused interview session."""
    logger.info(f"Resuming interview session {session_id}")
    update_data = InterviewSessionUpdate(status="interviewing")
    session = interview_service.update_session(db, session_id, update_data)
    return convert_session_to_schema(session, db)


@router.post("/{session_id}/end", response_model=InterviewSessionSchema)
async def end_interview_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    End an interview session.

    Marks the session as ended and triggers Insight Memo generation
    in the background (if session has a project_id).
    """
    logger.info(f"Ending interview session {session_id}")
    update_data = InterviewSessionUpdate(status="ended")
    session = interview_service.update_session(db, session_id, update_data)

    if session.interview_round_id:
        from app.services.interview_round_aggregate_service import interview_round_aggregate_service

        interview_round_aggregate_service.invalidate(db, session.interview_round_id)

    # Trigger Insight Memo generation in background
    if session.project_id:
        background_tasks.add_task(_generate_insight_memo_background, session_id)

    return convert_session_to_schema(session, db)


def _generate_insight_memo_background(session_id: str):
    """Background task: generate Insight Memo after interview ends."""
    from app.db.session import SessionLocal
    from app.services.evidence_matrix_service import evidence_matrix_service
    from app.services.insight_memo_service import insight_memo_service

    db = SessionLocal()
    try:
        memo = insight_memo_service.generate_memo(db, session_id)
        logger.info(f"Generated insight memo {memo.id} for session {session_id}")

        # Refresh project outputs from the rebuilt round aggregate.
        if memo.project_id:
            evidence_matrix_service.update_matrix(db, memo.project_id)
            logger.info(f"Refreshed evidence matrix for project {memo.project_id}")
    except Exception as e:
        logger.error(f"Background insight memo generation failed for session {session_id}: {e}")
    finally:
        db.close()


@router.post("/{session_id}/prepare-theme")
async def prepare_theme(
    session_id: str,
    body: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Synchronously compile rubrics for a specific theme, then background-warm remaining themes.

    Body: {"themeId": "theme_xxx"}

    The first call (for page 1) blocks until that theme's cards have compiled rubrics.
    After returning, remaining themes are queued for background prewarming in order.
    """
    from fastapi import HTTPException

    from app.models.question_card import QuestionCard
    from app.services.question_rubric_service import question_rubric_service

    theme_id = body.get("themeId")
    if not theme_id:
        raise HTTPException(status_code=400, detail="themeId is required")

    session = interview_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Compile rubrics for the requested theme (blocking)
    cards = (
        db.query(QuestionCard)
        .filter(
            QuestionCard.interview_theme_id == theme_id,
        )
        .order_by(QuestionCard.order_index)
        .all()
    )

    if cards:
        question_rubric_service.pre_warm_rubrics(db, cards)

    # Queue background prewarming for remaining themes in order
    background_tasks.add_task(_prewarm_remaining_themes_sync, session.document_id, theme_id)

    return {
        "themeId": theme_id,
        "cardsReady": len(cards),
        "status": "ready",
    }


def _prewarm_remaining_themes_sync(document_id: str, exclude_theme_id: str):
    """Background: prewarm rubrics for all themes except the one already done, in order."""
    from app.db.session import SessionLocal
    from app.models.interview_theme import InterviewTheme
    from app.models.question_card import QuestionCard
    from app.services.question_rubric_service import question_rubric_service

    db = SessionLocal()
    try:
        themes = (
            db.query(InterviewTheme)
            .filter(
                InterviewTheme.document_id == document_id,
                InterviewTheme.is_enabled == True,
                InterviewTheme.id != exclude_theme_id,
            )
            .order_by(InterviewTheme.order_index)
            .all()
        )

        for theme in themes:
            cards = (
                db.query(QuestionCard)
                .filter(
                    QuestionCard.interview_theme_id == theme.id,
                )
                .all()
            )
            if cards:
                question_rubric_service.pre_warm_rubrics(db, cards)
                logger.info(
                    f"Background pre-warmed rubrics for theme {theme.id} ({len(cards)} cards)"
                )
    except Exception as e:
        logger.warning(f"Background rubric pre-warm failed: {e}")
    finally:
        db.close()
