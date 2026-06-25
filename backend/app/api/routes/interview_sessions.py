"""Interview session routes."""

import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.interview import (
    InterviewCardStateSchema,
    InterviewCardStateUpdate,
    InterviewSessionCreate,
    InterviewSessionListResponse,
    InterviewSessionSchema,
    InterviewSessionUpdate,
    InterviewSessionWithDocument,
    PartialTranscriptMatchCreate,
    UtteranceCreate,
    UtteranceSchema,
)
from app.services.billing_service import billing_service
from app.services.interview_service import interview_service
from app.services.report_analytics_service import report_analytics_service
from app.services.report_export_service import report_export_service

logger = logging.getLogger(__name__)

router = APIRouter()


def convert_session_to_schema(session, db: Optional[Session] = None) -> InterviewSessionSchema:
    """Convert session model to schema."""
    usage = (
        billing_service.summarize_session(db, session.id) if db else billing_service.empty_summary()
    )

    # Calculate duration
    duration = None
    if session.started_at:
        duration = interview_service.calculate_active_duration(session)

    return InterviewSessionSchema(
        id=session.id,
        prepSessionId=session.prep_session_id,
        documentId=session.document_id,
        userId=session.user_id,
        status=session.status,
        currentSectionId=session.current_section_id,
        startedAt=session.started_at,
        endedAt=session.ended_at,
        pausedAt=session.paused_at,
        pausedDurationSeconds=session.paused_duration_seconds or 0,
        createdAt=session.created_at,
        duration=duration,
        costUsd=usage["totalCostUsd"],
        aiUsage=usage,
    )


def convert_utterance_to_schema(utterance) -> UtteranceSchema:
    """Convert utterance model to schema.

    Handles LiveUtterance, FinalUtterance, and legacy Utterance.
    """
    realtime_id = getattr(utterance, "realtime_event_id", None) or getattr(
        utterance, "realtime_item_id", None
    )
    section_id = getattr(utterance, "section_id", None) or getattr(utterance, "theme_id", None)

    # FinalUtterance uses speaker_role/speaker_display_name instead of speaker
    speaker = (
        getattr(utterance, "speaker", None)
        or getattr(utterance, "speaker_role", None)
        or getattr(utterance, "speaker_display_name", None)
        or "unknown"
    )

    return UtteranceSchema(
        id=utterance.id,
        sessionId=utterance.session_id,
        sectionId=section_id,
        speaker=speaker,
        transcript=utterance.transcript,
        startedAt=getattr(utterance, "started_at", None),
        endedAt=getattr(utterance, "ended_at", None),
        realtimeItemId=realtime_id,
        createdAt=getattr(utterance, "created_at", None),
    )


def convert_card_state_to_schema(card_state) -> InterviewCardStateSchema:
    """Convert card state model to schema."""
    return InterviewCardStateSchema(
        id=card_state.id,
        sessionId=card_state.session_id,
        questionCardId=card_state.question_card_id,
        status=card_state.status,
        confidence=float(card_state.confidence) if card_state.confidence else None,
        answeredAt=card_state.answered_at,
        evidenceTranscript=card_state.evidence_transcript,
        evidence=card_state.evidence,
        createdAt=card_state.created_at,
        updatedAt=card_state.updated_at,
    )


@router.get("/", response_model=InterviewSessionListResponse)
async def list_interview_sessions(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    project_id: Optional[str] = Query(None, alias="projectId"),
    db: Session = Depends(get_db),
):
    """
    List interview sessions with pagination.

    Query parameters:
    - limit: Number of sessions to return (1-1000, default 50)
    - offset: Number of sessions to skip (for pagination)
    - projectId: Optional filter by project
    """
    logger.info(
        f"Listing interview sessions: limit={limit}, offset={offset}, project_id={project_id}"
    )

    # For MVP, use default user
    user_id = "user_default"

    result = interview_service.list_sessions(
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset,
        project_id=project_id,
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
    from app.models.interview_theme import InterviewTheme
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
    """Update interview session status or current section."""
    logger.info(f"Updating interview session {session_id}")
    session = interview_service.update_session(db, session_id, update_data)
    return convert_session_to_schema(session, db)


@router.patch("/{session_id}/current-section", response_model=InterviewSessionSchema)
async def update_current_section(
    session_id: str, section_id: str = Body(..., embed=True), db: Session = Depends(get_db)
):
    """
    Update current section in interview session.

    This triggers section transition logic and may update card states
    (e.g., mark pending "must" cards as at_risk).
    """
    logger.info(f"Updating current section for session {session_id} to {section_id}")

    update_data = InterviewSessionUpdate(currentSectionId=section_id)
    session = interview_service.update_session(db, session_id, update_data)

    return convert_session_to_schema(session, db)


@router.post(
    "/{session_id}/utterances", status_code=status.HTTP_201_CREATED, response_model=UtteranceSchema
)
async def create_utterance(
    session_id: str,
    utterance: UtteranceCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a new utterance (transcribed speech segment).

    This endpoint receives transcripts from the frontend Realtime client
    and stores them for answer evaluation.

    Phase 1: Now writes to live_utterances instead of utterances.
    The endpoint URL remains the same for backwards compatibility.
    """
    # Speaker label is informational only (filled by diarize channel later).
    # Evaluation is speaker-agnostic — any speech triggers card matching.
    if not utterance.speaker:
        utterance.speaker = "pending"

    logger.info(f"Creating utterance for session {session_id}: {utterance.transcript[:50]}...")

    try:
        utterance_obj = await run_in_threadpool(
            interview_service.create_utterance,
            db,
            session_id,
            utterance,
        )

        theme_id = utterance.themeId or getattr(utterance_obj, "section_id", None)
        background_tasks.add_task(
            process_utterance_evaluation_background,
            session_id,
            utterance_obj.id,
            utterance_obj.transcript,
            theme_id,
            utterance_obj.speaker or "pending",
            utterance.askedCardId,
        )

        return convert_utterance_to_schema(utterance_obj)
    except ValueError as e:
        # Session status validation error
        logger.warning(f"Invalid session status for utterance creation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating utterance: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create utterance: {str(e)}")


_EVALUATION_DEBOUNCE_SECONDS = 1.5


def process_utterance_evaluation_background(
    session_id: str,
    utterance_id: str,
    transcript: str,
    section_id: Optional[str],
    speaker: str,
    asked_card_id: Optional[str] = None,
):
    """Background task to process utterance evaluation with debounce.

    Waits briefly, then checks if newer utterances have arrived.
    If yes, skips (the newer task will evaluate with more context).
    """
    import time

    from app.db.session import SessionLocal
    from app.models.live_utterance import LiveUtterance
    from app.services.answer_evaluation_engine import answer_evaluation_engine
    from app.services.event_service import event_service

    time.sleep(_EVALUATION_DEBOUNCE_SECONDS)

    db = SessionLocal()
    try:
        # Check if newer utterances arrived during debounce window
        latest_utt = (
            db.query(LiveUtterance)
            .filter(
                LiveUtterance.session_id == session_id,
                LiveUtterance.is_partial == False,
            )
            .order_by(LiveUtterance.sequence_index.desc())
            .first()
        )

        if latest_utt and latest_utt.id != utterance_id:
            logger.info(
                f"Debounce: skipping evaluation for {utterance_id}, "
                f"newer utterance {latest_utt.id} will handle it"
            )
            return

        if not section_id:
            from app.models.interview_session import InterviewSession as IS
            from app.models.interview_theme import InterviewTheme

            session_obj = db.query(IS).filter(IS.id == session_id).first()
            if session_obj:
                first_theme = (
                    db.query(InterviewTheme)
                    .filter(
                        InterviewTheme.document_id == session_obj.document_id,
                        InterviewTheme.is_enabled == True,
                    )
                    .order_by(InterviewTheme.order_index)
                    .first()
                )
                if first_theme:
                    section_id = first_theme.id
            if not section_id:
                logger.warning(
                    f"Utterance {utterance_id} has no section_id and no fallback theme, skipping evaluation"
                )
                return

        # Process utterance and get card state updates
        updates = answer_evaluation_engine.process_utterance(
            db=db,
            session_id=session_id,
            utterance_id=utterance_id,
            utterance_text=transcript,
            section_id=section_id,
            speaker=speaker,
            asked_card_id=asked_card_id,
        )

        # If question was detected and no card was auto-activated, emit candidates
        if (
            not updates
            and not asked_card_id
            and answer_evaluation_engine._is_question_like(transcript)
        ):
            candidates = answer_evaluation_engine.find_candidate_cards(
                db, session_id, section_id or "", transcript, top_k=3
            )
            if candidates:
                event_service.publish_sync(
                    session_id,
                    {
                        "type": "QUESTION_CARD_CANDIDATES",
                        "utterance_id": utterance_id,
                        "candidates": candidates,
                    },
                )

        # Emit events based on activation/completion separation
        for update in updates:
            new_status = update["new_status"]
            old_status = update["old_status"]
            completion_score = update.get("completion_score", 0.0)
            activation_score = update.get("activation_score", 0.0)

            # Determine event type
            if new_status == "sufficient":
                event_type = "CARD_COVERED"
            elif new_status == "probably_sufficient":
                event_type = "CARD_PROGRESS_CHANGED"
            elif new_status == "listening" and old_status == "pending":
                event_type = "CARD_TOPIC_DETECTED"
            elif new_status == "listening":
                event_type = "CARD_LISTENING"
            elif new_status == "at_risk":
                event_type = "CARD_AT_RISK"
            else:
                event_type = "CARD_LISTENING"

            event_service.publish_sync(
                session_id,
                {
                    "type": event_type,
                    "card_id": update["card_id"],
                    "old_status": old_status,
                    "new_status": new_status,
                    "activation_score": activation_score,
                    "completion_score": completion_score,
                    "confidence": update["confidence"],
                    "evidence": update.get("evidence"),
                    "evidenceTranscript": update.get("evidence_transcript"),
                    "evaluationSeq": update.get("evaluation_seq"),
                },
            )

            # Emit granular evidence events only for real answer progress
            if completion_score > 0:
                criterion_evals = (update.get("judgment") or {}).get("criterion_evaluations", [])
                for crit_eval in criterion_evals:
                    crit_status = crit_eval.get("status", "not_addressed")
                    if crit_status in ("not_addressed",):
                        continue
                    event_service.publish_sync(
                        session_id,
                        {
                            "type": "CARD_EVIDENCE_ADDED",
                            "card_id": update["card_id"],
                            "criterion_id": crit_eval.get("criterion_id"),
                            "status": crit_status,
                            "evidence_quote": (crit_eval.get("evidence_quotes") or [None])[0],
                            "completion_score": completion_score,
                            "evaluationSeq": update.get("evaluation_seq"),
                        },
                    )

    except Exception as e:
        logger.error(f"Error processing utterance evaluation: {str(e)}", exc_info=True)
    finally:
        db.close()


@router.patch("/{session_id}/utterances/{utterance_id}/speaker")
async def update_utterance_speaker(
    session_id: str,
    utterance_id: str,
    body: dict,
    db: Session = Depends(get_db),
):
    """Update speaker label on an utterance (from diarization). Informational only."""
    from app.models.utterance import Utterance

    new_speaker = body.get("speaker")
    if not new_speaker:
        raise HTTPException(status_code=400, detail="speaker is required")

    utterance = (
        db.query(Utterance)
        .filter(
            Utterance.id == utterance_id,
            Utterance.session_id == session_id,
        )
        .first()
    )
    if not utterance:
        raise HTTPException(status_code=404, detail="Utterance not found")

    old_speaker = utterance.speaker
    utterance.speaker = new_speaker
    db.commit()

    return {"id": utterance_id, "speaker": new_speaker, "changed": old_speaker != new_speaker}


@router.get("/{session_id}/utterances", response_model=List[UtteranceSchema])
async def get_session_utterances(
    session_id: str,
    section_id: Optional[str] = Query(None, alias="sectionId"),
    speaker: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get utterances for an interview session, optionally filtered by section and/or speaker."""
    logger.info(f"Retrieving utterances for session {session_id}")
    utterances = interview_service.get_utterances(
        db=db, session_id=session_id, section_id=section_id, speaker=speaker, limit=limit
    )
    return [convert_utterance_to_schema(u) for u in utterances]


@router.post("/{session_id}/partial-transcript-match")
async def match_partial_transcript(
    session_id: str,
    partial: PartialTranscriptMatchCreate,
    background_tasks: BackgroundTasks,
):
    """
    Match an in-flight streaming transcript without storing it as an utterance.

    The completed transcript still goes through /utterances for durable storage.
    """
    transcript = partial.transcript.strip()
    if len(transcript) < 8:
        return {"accepted": False, "reason": "partial transcript too short"}

    theme_id = partial.themeId or partial.sectionId
    background_tasks.add_task(
        process_partial_transcript_evaluation_background,
        session_id,
        transcript,
        theme_id,
        partial.speaker,
        partial.activeCardId,
    )
    return {"accepted": True}


def process_partial_transcript_evaluation_background(
    session_id: str,
    transcript: str,
    section_id: Optional[str],
    speaker: str,
    active_card_id: Optional[str] = None,
):
    """Background task to process partial transcript evaluation."""
    from app.db.session import SessionLocal
    from app.services.answer_evaluation_engine import answer_evaluation_engine
    from app.services.event_service import event_service

    db = SessionLocal()
    try:
        if not section_id:
            logger.warning(f"Partial transcript has no section_id, skipping evaluation")
            return

        # Process partial transcript
        updates = answer_evaluation_engine.process_partial_transcript(
            db=db,
            session_id=session_id,
            transcript_text=transcript,
            section_id=section_id,
            speaker=speaker,
            active_card_id=active_card_id,
        )

        # Emit events for card state changes (use event names frontend expects)
        STATUS_TO_EVENT = {
            "sufficient": "CARD_COVERED",
            "probably_sufficient": "CARD_PROBABLY_COVERED",
            "listening": "CARD_LISTENING",
            "at_risk": "CARD_AT_RISK",
            "skipped": "CARD_SKIPPED",
        }
        for update in updates:
            event_type = STATUS_TO_EVENT.get(update["new_status"], "CARD_LISTENING")
            event_service.publish_sync(
                session_id,
                {
                    "type": event_type,
                    "card_id": update["card_id"],
                    "old_status": update["old_status"],
                    "new_status": update["new_status"],
                    "confidence": update["confidence"],
                    "evidence": update.get("evidence"),
                    "evidenceTranscript": update.get("evidence_transcript"),
                    "evaluationSeq": update.get("evaluation_seq"),  # Phase 2: for versioned SSE
                },
            )

    except Exception as e:
        logger.error(f"Error processing partial transcript evaluation: {str(e)}", exc_info=True)
    finally:
        db.close()


@router.get("/{session_id}/card-states", response_model=List[InterviewCardStateSchema])
async def get_session_card_states(session_id: str, db: Session = Depends(get_db)):
    """Get all card states for an interview session."""
    logger.info(f"Retrieving card states for session {session_id}")
    card_states = interview_service.get_all_card_states(db, session_id)
    return [convert_card_state_to_schema(cs) for cs in card_states]


@router.patch("/{session_id}/card-states/{card_state_id}", response_model=InterviewCardStateSchema)
async def update_session_card_state(
    session_id: str,
    card_state_id: str,
    update_data: InterviewCardStateUpdate,
    db: Session = Depends(get_db),
):
    """Manually update a card state during an interview."""
    logger.info(f"Updating card state {card_state_id} for session {session_id}")
    card_state = interview_service.update_card_state(
        db=db, session_id=session_id, card_state_id=card_state_id, update_data=update_data
    )
    return convert_card_state_to_schema(card_state)


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

        # Also refresh evidence matrix if project exists
        if memo.project_id:
            evidence_matrix_service.update_matrix(db, memo.project_id)
            logger.info(f"Refreshed evidence matrix for project {memo.project_id}")
    except Exception as e:
        logger.error(f"Background insight memo generation failed for session {session_id}: {e}")
    finally:
        db.close()


@router.get("/{session_id}/events")
async def get_interview_events(session_id: str, db: Session = Depends(get_db)):
    """
    Get real-time events for an interview session (SSE or WebSocket).

    Events: CARD_STATE_UPDATED, CARD_SUFFICIENT, CARD_AT_RISK, etc.
    """
    return {
        "message": "Use /api/events/sessions/{sessionId}/stream for SSE event stream",
        "sessionId": session_id,
    }


@router.get("/{session_id}/log")
async def get_session_log(session_id: str, db: Session = Depends(get_db)):
    """Get a unified chronological timeline of everything that happened in a session."""
    from app.models.ai_usage_event import AIUsageEvent
    from app.models.card_coverage_evaluation import CardCoverageEvaluation
    from app.models.final_utterance import FinalUtterance
    from app.models.interview_session import InterviewCardState, InterviewSession
    from app.models.live_utterance import LiveUtterance
    from app.models.utterance import Utterance

    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    events = []

    if session.started_at:
        events.append(
            {"type": "session", "action": "started", "timestamp": session.started_at.isoformat()}
        )
    if session.paused_at:
        events.append(
            {"type": "session", "action": "paused", "timestamp": session.paused_at.isoformat()}
        )
    if session.ended_at:
        events.append(
            {"type": "session", "action": "ended", "timestamp": session.ended_at.isoformat()}
        )

    # Prefer final_utterances, then live_utterances, then old utterances
    final_utts = (
        db.query(FinalUtterance)
        .filter(FinalUtterance.session_id == session_id)
        .order_by(FinalUtterance.sequence_index)
        .all()
    )
    if final_utts:
        for u in final_utts:
            events.append(
                {
                    "type": "utterance",
                    "speaker": u.speaker_display_name or u.speaker_label,
                    "transcript": u.transcript,
                    "timestamp": (u.started_at or u.created_at).isoformat(),
                }
            )
    else:
        live_utts = (
            db.query(LiveUtterance)
            .filter(LiveUtterance.session_id == session_id, LiveUtterance.is_partial == False)
            .order_by(LiveUtterance.created_at)
            .all()
        )
        if live_utts:
            for u in live_utts:
                events.append(
                    {
                        "type": "utterance",
                        "speaker": u.speaker,
                        "transcript": u.transcript,
                        "timestamp": (u.started_at or u.created_at).isoformat(),
                    }
                )
        else:
            old_utts = (
                db.query(Utterance)
                .filter(Utterance.session_id == session_id)
                .order_by(Utterance.created_at)
                .all()
            )
            for u in old_utts:
                events.append(
                    {
                        "type": "utterance",
                        "speaker": u.speaker,
                        "transcript": u.transcript,
                        "timestamp": (u.started_at or u.created_at).isoformat(),
                    }
                )

    # Card coverage: prefer CardCoverageEvaluation, fallback to InterviewCardState
    coverage_evals = (
        db.query(CardCoverageEvaluation)
        .filter(CardCoverageEvaluation.session_id == session_id)
        .order_by(CardCoverageEvaluation.created_at)
        .all()
    )
    if coverage_evals:
        for ce in coverage_evals:
            events.append(
                {
                    "type": "card_update",
                    "cardId": ce.card_id,
                    "status": ce.state,
                    "basisType": ce.basis_type,
                    "confidence": float(ce.confidence) if ce.confidence else None,
                    "evidence": ce.evidence,
                    "timestamp": ce.created_at.isoformat(),
                }
            )
    else:
        card_states = (
            db.query(InterviewCardState).filter(InterviewCardState.session_id == session_id).all()
        )
        for cs in card_states:
            if cs.status != "pending":
                events.append(
                    {
                        "type": "card_update",
                        "cardId": cs.question_card_id,
                        "status": cs.status,
                        "confidence": float(cs.confidence) if cs.confidence else None,
                        "evidenceTranscript": cs.evidence_transcript,
                        "timestamp": (cs.answered_at or cs.updated_at).isoformat(),
                    }
                )

    ai_events = (
        db.query(AIUsageEvent)
        .filter(AIUsageEvent.interview_session_id == session_id)
        .order_by(AIUsageEvent.created_at)
        .all()
    )
    for ae in ai_events:
        events.append(
            {
                "type": "ai_usage",
                "operation": ae.operation,
                "model": ae.model,
                "totalTokens": ae.total_tokens,
                "costUsd": float(ae.cost_usd),
                "timestamp": ae.created_at.isoformat(),
            }
        )

    events.sort(key=lambda e: e["timestamp"])

    return {
        "sessionId": session_id,
        "status": session.status,
        "startedAt": session.started_at.isoformat() if session.started_at else None,
        "endedAt": session.ended_at.isoformat() if session.ended_at else None,
        "events": events,
    }


@router.get("/{session_id}/report")
async def get_session_report(session_id: str, db: Session = Depends(get_db)):
    """Get post-interview analytics report."""
    logger.info(f"Getting session report for {session_id}")

    try:
        return report_analytics_service.generate_comprehensive_report(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error generating session report: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report",
        )


@router.post("/{session_id}/outputs/generate")
async def generate_session_outputs(session_id: str, db: Session = Depends(get_db)):
    """Generate BRD document and transcript after interview ends.

    Returns structured BRD (markdown) and full transcript (markdown).
    BRD sections with insufficient evidence are marked as '待補'.
    """
    from app.services.brd_generation_service import brd_generation_service

    logger.info(f"Generating BRD and transcript for session {session_id}")
    try:
        result = brd_generation_service.generate_outputs(db, session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{session_id}/report")
async def generate_session_report(session_id: str, db: Session = Depends(get_db)):
    """Generate post-interview analytics report.

    Kept for compatibility with clients that already call POST.
    """
    return await get_session_report(session_id, db)


@router.post("/{session_id}/report/export/{export_format}")
async def export_session_report(
    session_id: str,
    export_format: str,
    db: Session = Depends(get_db),
):
    """Export a session report as JSON or PDF and return a presigned download URL."""
    logger.info(f"Exporting {export_format} session report for {session_id}")

    if export_format not in {"json", "pdf"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="export_format must be either 'json' or 'pdf'",
        )

    try:
        return report_export_service.export_report(db, session_id, export_format)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error exporting session report: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export session report",
        )


@router.get("/{session_id}/analytics")
async def get_session_analytics(session_id: str, db: Session = Depends(get_db)):
    """Get comprehensive analytics for a session - Phase 6.

    Returns:
        - Transcription stats (live vs final utterance counts, alignment match rate)
        - Card coverage stats (provisional vs final, drift analysis)
        - Q/A stats (questions answered, card match rate)
        - AI usage stats (model call counts, tokens, costs)
        - Quality metrics (evidence quote rate, prefilter effectiveness)
    """
    from sqlalchemy import func

    from app.models.ai_usage_event import AIUsageEvent
    from app.models.card_coverage_evaluation import CardCoverageEvaluation
    from app.models.final_utterance import FinalUtterance
    from app.models.interview_session import InterviewSession
    from app.models.live_utterance import LiveUtterance
    from app.models.question_answer import QuestionAnswer
    from app.models.question_card import QuestionCard
    from app.models.question_instance import QuestionInstance
    from app.models.utterance_alignment import UtteranceAlignment

    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # === Transcription Stats ===
    live_count = (
        db.query(LiveUtterance)
        .filter(
            LiveUtterance.session_id == session_id,
            LiveUtterance.is_partial == False,
        )
        .count()
    )

    final_count = db.query(FinalUtterance).filter(FinalUtterance.session_id == session_id).count()

    speakers = (
        db.query(func.count(func.distinct(FinalUtterance.speaker_label)))
        .filter(FinalUtterance.session_id == session_id)
        .scalar()
        or 0
    )

    # Alignment match rate
    total_alignments = (
        db.query(UtteranceAlignment).filter(UtteranceAlignment.session_id == session_id).count()
    )

    matched_alignments = (
        db.query(UtteranceAlignment)
        .filter(
            UtteranceAlignment.session_id == session_id,
            UtteranceAlignment.final_utterance_id.isnot(None),
        )
        .count()
    )

    alignment_rate = (
        round(matched_alignments / total_alignments, 3) if total_alignments > 0 else None
    )

    # === Card Coverage Stats ===
    total_cards = (
        db.query(QuestionCard).filter(QuestionCard.document_id == session.document_id).count()
        if session.document_id
        else 0
    )

    def coverage_breakdown(basis_type):
        """Get latest evaluation per card for given basis type."""
        evals = (
            db.query(CardCoverageEvaluation)
            .filter(
                CardCoverageEvaluation.session_id == session_id,
                CardCoverageEvaluation.basis_type == basis_type,
            )
            .all()
        )

        # Get latest eval per card (highest evaluation_seq)
        latest = {}
        for e in evals:
            if e.card_id not in latest or e.evaluation_seq > latest[e.card_id].evaluation_seq:
                latest[e.card_id] = e

        counts = {"sufficient": 0, "probably_sufficient": 0, "listening": 0, "pending": 0}
        for e in latest.values():
            if e.state in counts:
                counts[e.state] += 1
            else:
                # Map any unknown states to pending
                counts["pending"] += 1

        return counts

    prov = coverage_breakdown("live")
    final = coverage_breakdown("final")

    # Drift analysis (compare latest live vs latest final per card)
    live_evals = (
        db.query(CardCoverageEvaluation)
        .filter(
            CardCoverageEvaluation.session_id == session_id,
            CardCoverageEvaluation.basis_type == "live",
        )
        .all()
    )

    final_evals = (
        db.query(CardCoverageEvaluation)
        .filter(
            CardCoverageEvaluation.session_id == session_id,
            CardCoverageEvaluation.basis_type == "final",
        )
        .all()
    )

    # Build latest eval maps
    latest_live = {}
    for e in live_evals:
        if e.card_id not in latest_live or e.evaluation_seq > latest_live[e.card_id].evaluation_seq:
            latest_live[e.card_id] = e

    latest_final = {}
    for e in final_evals:
        if (
            e.card_id not in latest_final
            or e.evaluation_seq > latest_final[e.card_id].evaluation_seq
        ):
            latest_final[e.card_id] = e

    # Compare states
    STATE_ORDER = {"pending": 0, "listening": 1, "probably_sufficient": 2, "sufficient": 3}
    upgraded = 0
    downgraded = 0
    unchanged = 0

    for card_id in set(latest_live.keys()) | set(latest_final.keys()):
        live_state = latest_live.get(card_id)
        final_state = latest_final.get(card_id)

        if not live_state or not final_state:
            unchanged += 1  # Only exists in one basis
            continue

        live_level = STATE_ORDER.get(live_state.state, 0)
        final_level = STATE_ORDER.get(final_state.state, 0)

        if final_level > live_level:
            upgraded += 1
        elif final_level < live_level:
            downgraded += 1
        else:
            unchanged += 1

    # === Q/A Stats ===
    q_count = db.query(QuestionInstance).filter(QuestionInstance.session_id == session_id).count()

    qa_statuses = (
        db.query(QuestionAnswer.answer_status, func.count(QuestionAnswer.id))
        .filter(QuestionAnswer.session_id == session_id)
        .group_by(QuestionAnswer.answer_status)
        .all()
    )

    qa_stats = {status: count for status, count in qa_statuses}

    card_matched = (
        db.query(QuestionInstance)
        .filter(
            QuestionInstance.session_id == session_id,
            QuestionInstance.card_id.isnot(None),
        )
        .count()
    )

    card_match_rate = round(card_matched / q_count, 3) if q_count > 0 else None

    # === AI Usage Stats ===
    ai_events = db.query(AIUsageEvent).filter(AIUsageEvent.interview_session_id == session_id).all()

    nano_count = sum(1 for e in ai_events if e.model and "nano" in e.model.lower())
    mini_count = sum(1 for e in ai_events if e.model and "mini" in e.model.lower())
    total_tokens = sum(e.total_tokens or 0 for e in ai_events)
    total_cost = sum(float(e.cost_usd) if e.cost_usd else 0 for e in ai_events)

    # === Quality Metrics ===
    # Evidence quote rate (for final sufficient cards)
    final_sufficient = (
        db.query(CardCoverageEvaluation)
        .filter(
            CardCoverageEvaluation.session_id == session_id,
            CardCoverageEvaluation.basis_type == "final",
            CardCoverageEvaluation.state == "sufficient",
        )
        .all()
    )

    # Get latest sufficient per card
    latest_sufficient = {}
    for e in final_sufficient:
        if (
            e.card_id not in latest_sufficient
            or e.evaluation_seq > latest_sufficient[e.card_id].evaluation_seq
        ):
            latest_sufficient[e.card_id] = e

    with_evidence = sum(1 for e in latest_sufficient.values() if e.evidence and len(e.evidence) > 0)
    evidence_rate = round(with_evidence / len(latest_sufficient), 3) if latest_sufficient else None

    # Candidate cards per evaluation (average from card coverage evaluations)
    # Note: This would need to be tracked during evaluation; for now, return null
    candidate_cards_per_eval = None
    prefilter_reduction_rate = None

    return {
        "sessionId": session_id,
        "transcription": {
            "liveUtteranceCount": live_count,
            "finalUtteranceCount": final_count,
            "speakerCount": speakers,
            "transcriptStatus": session.transcript_status,
            "alignmentMatchRate": alignment_rate,
        },
        "cardCoverage": {
            "totalCards": total_cards,
            "provisionalCoverage": prov,
            "finalCoverage": final,
            "provisionalToFinalDrift": {
                "upgraded": upgraded,
                "downgraded": downgraded,
                "unchanged": unchanged,
            },
        },
        "qa": {
            "totalQuestions": q_count,
            "answered": qa_stats.get("answered", 0),
            "partiallyAnswered": qa_stats.get("partially_answered", 0),
            "notAnswered": qa_stats.get("not_answered", 0),
            "cardMatchRate": card_match_rate,
        },
        "aiUsage": {
            "nanoCallCount": nano_count,
            "miniCallCount": mini_count,
            "totalTokens": total_tokens,
            "totalCostUsd": round(total_cost, 6),
            "averageEvaluationLatencyMs": None,  # Would need to track evaluation times
        },
        "quality": {
            "candidateCardsPerEvaluation": candidate_cards_per_eval,
            "prefilterReductionRate": prefilter_reduction_rate,
            "evidenceQuoteRate": evidence_rate,
        },
    }


@router.post("/{session_id}/apply-role-filter")
async def apply_role_filter(session_id: str, db: Session = Depends(get_db)):
    """Apply role filtering to a session based on its stakeholder profile.

    Marks cards as not_applicable_for_role if they don't match the
    stakeholder's expertise. Call this after setting a stakeholder
    on the session.
    """
    from app.services.role_filter_service import role_filter_service

    result = role_filter_service.apply_role_filter_to_session(db, session_id)
    if result.get("skipped"):
        raise HTTPException(status_code=400, detail="Session has no stakeholder profile assigned")
    return result


@router.post("/{session_id}/brief")
async def generate_interview_brief(session_id: str, db: Session = Depends(get_db)):
    """Generate an interview brief for a session.

    Requires the session to have project_id and stakeholder_profile_id set.
    """
    from app.services.interview_brief_service import interview_brief_service

    try:
        brief = interview_brief_service.generate_brief(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _brief_to_response(brief)


@router.get("/{session_id}/brief")
async def get_interview_brief(session_id: str, db: Session = Depends(get_db)):
    """Get the interview brief for a session."""
    from app.services.interview_brief_service import interview_brief_service

    brief = interview_brief_service.get_brief(db, session_id)
    if not brief:
        raise HTTPException(status_code=404, detail="No brief found for this session")

    return _brief_to_response(brief)


def _brief_to_response(brief) -> dict:
    """Convert InterviewBrief to API response."""
    return {
        "id": brief.id,
        "sessionId": brief.session_id,
        "stakeholderProfileId": brief.stakeholder_profile_id,
        "projectId": brief.project_id,
        "interviewObjective": brief.interview_objective,
        "recommendedTopics": brief.recommended_topics or [],
        "excludedTopics": brief.excluded_topics or [],
        "suggestedQuestions": brief.suggested_questions or [],
        "followUpFromPriorInterviews": brief.follow_up_from_prior_interviews or [],
        "applicableCardIds": brief.applicable_card_ids or [],
        "notApplicableCards": brief.not_applicable_cards or [],
        "timeEstimateMinutes": brief.time_estimate_minutes,
        "notes": brief.notes,
        "generatedAt": brief.generated_at.isoformat() if brief.generated_at else None,
    }


# --- Human-in-the-loop Card Routing ---


@router.post("/{session_id}/route-question")
async def route_question(session_id: str, body: dict, db: Session = Depends(get_db)):
    """Find top candidate cards for a question. Does not auto-activate."""
    from app.services.answer_evaluation_engine import answer_evaluation_engine

    text = body.get("text", "")
    theme_id = body.get("themeId")
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    session = interview_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    section_id = theme_id or session.current_section_id or session.current_theme_id
    if not section_id:
        raise HTTPException(status_code=400, detail="No theme/section context")

    candidates = answer_evaluation_engine.find_candidate_cards(
        db, session_id, section_id, text, top_k=3
    )
    return {"candidates": candidates}


@router.post("/{session_id}/active-card")
async def set_active_card(session_id: str, body: dict, db: Session = Depends(get_db)):
    """User confirms which card is currently being discussed."""
    import uuid
    from datetime import datetime

    from app.models.card_coverage_evaluation import CardCoverageEvaluation
    from app.models.interview_session import InterviewCardState
    from app.models.interview_session import InterviewSession as IS
    from app.services.event_service import event_service

    card_id = body.get("cardId")
    source = body.get("source", "user_confirmed")
    if not card_id:
        raise HTTPException(status_code=400, detail="cardId is required")

    session = db.query(IS).filter(IS.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update session active card
    session.active_card_id = card_id
    session.active_card_hint_id = card_id
    session.active_card_source = source
    session.active_card_confirmed_at = datetime.utcnow()

    # Activate the card (pending → listening)
    card_state = (
        db.query(InterviewCardState)
        .filter(
            InterviewCardState.session_id == session_id,
            InterviewCardState.question_card_id == card_id,
        )
        .first()
    )

    result_status = "listening"
    if card_state and card_state.status == "pending":
        card_state.status = "listening"
        card_state.activation_score = 1.0
        card_state.updated_at = datetime.utcnow()
        result_status = "listening"
    elif card_state:
        result_status = card_state.status

    # Replay buffered answers if any
    buffer = session.pending_answer_buffer or []
    session.pending_answer_buffer = None
    db.commit()

    # Emit event
    event_service.publish_sync(
        session_id,
        {
            "type": "ACTIVE_CARD_CHANGED",
            "card_id": card_id,
            "status": result_status,
            "source": source,
            "activation_score": 1.0,
            "completion_score": 0.0,
        },
    )

    # Replay buffered utterances against the confirmed card (idempotent: buffer already cleared above)
    if buffer:
        from app.models.live_utterance import LiveUtterance
        from app.services.answer_evaluation_engine import answer_evaluation_engine

        section_id = session.current_section_id or session.current_theme_id or ""
        for utt_id in buffer:
            utt = db.query(LiveUtterance).filter(LiveUtterance.id == utt_id).first()
            if not utt:
                continue
            updates = answer_evaluation_engine._evaluate_answer(
                db,
                session_id,
                utt.id,
                utt.transcript,
                section_id,
                utt.speaker or "interviewee",
            )
            for update in updates:
                new_status = update["new_status"]
                event_type = (
                    "CARD_COVERED" if new_status == "sufficient" else "CARD_PROGRESS_CHANGED"
                )
                event_service.publish_sync(
                    session_id,
                    {
                        "type": event_type,
                        "card_id": update["card_id"],
                        "old_status": update["old_status"],
                        "new_status": new_status,
                        "activation_score": update.get("activation_score", 1.0),
                        "completion_score": update.get("completion_score", 0),
                        "confidence": update["confidence"],
                        "evidence": update.get("evidence"),
                        "evidenceTranscript": update.get("evidence_transcript"),
                        "evaluationSeq": update.get("evaluation_seq"),
                    },
                )

        event_service.publish_sync(
            session_id,
            {
                "type": "ANSWER_BUFFER_REPLAYED",
                "card_id": card_id,
                "replayed_count": len(buffer),
            },
        )

    return {
        "cardId": card_id,
        "status": result_status,
        "activationScore": 1.0,
        "bufferedAnswersReplayed": len(buffer),
    }


@router.delete("/{session_id}/active-card")
async def clear_active_card(session_id: str, db: Session = Depends(get_db)):
    """Clear the active card."""
    from app.models.interview_session import InterviewSession as IS
    from app.services.event_service import event_service

    session = db.query(IS).filter(IS.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.active_card_id = None
    session.active_card_hint_id = None
    session.active_card_source = "cleared"
    session.pending_answer_buffer = None
    db.commit()

    event_service.publish_sync(session_id, {"type": "ACTIVE_CARD_CLEARED"})
    return {"ok": True}


@router.post("/{session_id}/cards/{card_id}/manual-complete")
async def manual_complete_card(
    session_id: str, card_id: str, body: dict, db: Session = Depends(get_db)
):
    """User manually marks a card as completed."""
    import uuid
    from datetime import datetime

    from app.models.card_coverage_evaluation import CardCoverageEvaluation
    from app.models.interview_session import InterviewCardState
    from app.services.event_service import event_service

    note = body.get("note", "")

    card_state = (
        db.query(InterviewCardState)
        .filter(
            InterviewCardState.session_id == session_id,
            InterviewCardState.question_card_id == card_id,
        )
        .first()
    )
    if not card_state:
        raise HTTPException(status_code=404, detail="Card state not found")

    old_status = card_state.status
    card_state.status = "sufficient"
    card_state.completion_source = "manual"
    card_state.manual_note = note or None
    card_state.completion_score = 1.0
    card_state.confidence = 1.0
    card_state.answered_at = datetime.utcnow()
    card_state.updated_at = datetime.utcnow()

    # Write audit record
    coverage_eval = CardCoverageEvaluation(
        id=f"cce_{uuid.uuid4().hex[:12]}",
        session_id=session_id,
        card_id=card_id,
        basis_type="live",
        transcript_revision_id=None,
        state="sufficient",
        confidence=1.0,
        covered_element_ids=[],
        missing_element_ids=[],
        evidence=[{"manual_note": note}] if note else [],
        evaluation_seq=999,
        model="manual",
        prompt_version=None,
        created_at=datetime.utcnow(),
    )
    db.add(coverage_eval)
    db.commit()

    event_service.publish_sync(
        session_id,
        {
            "type": "CARD_MANUALLY_COMPLETED",
            "card_id": card_id,
            "old_status": old_status,
            "new_status": "sufficient",
            "completion_source": "manual",
            "note": note,
        },
    )

    return {
        "cardId": card_id,
        "status": "sufficient",
        "completionSource": "manual",
    }


@router.post("/{session_id}/cards/{card_id}/undo-complete")
async def undo_complete_card(session_id: str, card_id: str, db: Session = Depends(get_db)):
    """Undo a manual completion — revert card to its previous state."""
    from datetime import datetime

    from app.models.interview_session import InterviewCardState
    from app.services.event_service import event_service

    card_state = (
        db.query(InterviewCardState)
        .filter(
            InterviewCardState.session_id == session_id,
            InterviewCardState.question_card_id == card_id,
        )
        .first()
    )
    if not card_state:
        raise HTTPException(status_code=404, detail="Card state not found")

    # Revert to listening (or pending if no activation)
    prev_status = "listening" if float(card_state.activation_score or 0) > 0 else "pending"
    card_state.status = prev_status
    card_state.completion_source = None
    card_state.manual_note = None
    card_state.confidence = float(card_state.completion_score or 0)
    card_state.updated_at = datetime.utcnow()
    db.commit()

    event_service.publish_sync(
        session_id,
        {
            "type": "CARD_UNDO_COMPLETED",
            "card_id": card_id,
            "new_status": prev_status,
        },
    )

    return {"cardId": card_id, "status": prev_status}
