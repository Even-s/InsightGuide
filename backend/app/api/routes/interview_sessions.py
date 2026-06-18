"""Interview session routes."""

import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Body, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.services.interview_service import interview_service
from app.services.billing_service import billing_service
from app.services.report_analytics_service import report_analytics_service
from app.services.report_export_service import report_export_service
from app.schemas.interview import (
    InterviewSessionSchema,
    InterviewSessionCreate,
    InterviewSessionUpdate,
    UtteranceSchema,
    UtteranceCreate,
    InterviewCardStateSchema,
    InterviewCardStateUpdate,
    InterviewSessionListResponse,
    InterviewSessionWithDocument,
    PartialTranscriptMatchCreate,
)

logger = logging.getLogger(__name__)

router = APIRouter()

def convert_session_to_schema(session, db: Optional[Session] = None) -> InterviewSessionSchema:
    """Convert session model to schema."""
    usage = billing_service.summarize_session(db, session.id) if db else billing_service.empty_summary()

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
    realtime_id = getattr(utterance, 'realtime_event_id', None) or getattr(utterance, 'realtime_item_id', None)
    section_id = getattr(utterance, 'section_id', None) or getattr(utterance, 'theme_id', None)

    # FinalUtterance uses speaker_role/speaker_display_name instead of speaker
    speaker = getattr(utterance, 'speaker', None) or getattr(utterance, 'speaker_role', None) or getattr(utterance, 'speaker_display_name', None) or 'unknown'

    return UtteranceSchema(
        id=utterance.id,
        sessionId=utterance.session_id,
        sectionId=section_id,
        speaker=speaker,
        transcript=utterance.transcript,
        startedAt=getattr(utterance, 'started_at', None),
        endedAt=getattr(utterance, 'ended_at', None),
        realtimeItemId=realtime_id,
        createdAt=getattr(utterance, 'created_at', None),
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
    logger.info(f"Listing interview sessions: limit={limit}, offset={offset}, project_id={project_id}")

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
    """Get interview session by ID. Pre-warms rubrics before returning."""
    logger.info(f"Retrieving interview session {session_id}")
    session = interview_service.get_session(db, session_id)

    # Pre-warm rubrics synchronously — frontend waits until all rubrics are ready
    if session and session.status in ("idle", "ready", "preparing"):
        await run_in_threadpool(_pre_warm_rubrics_sync, session.document_id)

    return convert_session_to_schema(session, db)


def _pre_warm_rubrics_sync(document_id: str):
    """Compile rubrics for all cards in a document (blocking)."""
    from app.db.session import SessionLocal
    from app.models.question_card import QuestionCard
    from app.services.question_rubric_service import question_rubric_service

    db = SessionLocal()
    try:
        cards = db.query(QuestionCard).filter(
            QuestionCard.document_id == document_id,
        ).all()
        if cards:
            question_rubric_service.pre_warm_rubrics(db, cards)
            logger.info(f"Pre-warmed rubrics for {len(cards)} cards (doc={document_id})")
    except Exception as e:
        logger.warning(f"Rubric pre-warm failed: {e}")
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

        theme_id = utterance.themeId or getattr(utterance_obj, 'section_id', None)
        # Always evaluate — speaker doesn't matter for card coverage
        background_tasks.add_task(
            process_utterance_evaluation_background,
            session_id,
            utterance_obj.id,
            utterance_obj.transcript,
            theme_id,
            utterance_obj.speaker or "pending",
        )

        return convert_utterance_to_schema(utterance_obj)
    except ValueError as e:
        # Session status validation error
        logger.warning(f"Invalid session status for utterance creation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating utterance: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create utterance: {str(e)}")


def process_utterance_evaluation_background(
    session_id: str,
    utterance_id: str,
    transcript: str,
    section_id: Optional[str],
    speaker: str,
):
    """Background task to process utterance evaluation."""
    from app.db.session import SessionLocal
    from app.services.answer_evaluation_engine import answer_evaluation_engine
    from app.services.event_service import event_service

    db = SessionLocal()
    try:
        if not section_id:
            from app.models.interview_session import InterviewSession as IS
            from app.models.interview_theme import InterviewTheme
            session_obj = db.query(IS).filter(IS.id == session_id).first()
            if session_obj:
                first_theme = db.query(InterviewTheme).filter(
                    InterviewTheme.document_id == session_obj.document_id,
                    InterviewTheme.is_enabled == True,
                ).order_by(InterviewTheme.order_index).first()
                if first_theme:
                    section_id = first_theme.id
            if not section_id:
                logger.warning(f"Utterance {utterance_id} has no section_id and no fallback theme, skipping evaluation")
                return

        # Process utterance and get card state updates
        updates = answer_evaluation_engine.process_utterance(
            db=db,
            session_id=session_id,
            utterance_id=utterance_id,
            utterance_text=transcript,
            section_id=section_id,
            speaker=speaker
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
                }
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

    utterance = db.query(Utterance).filter(
        Utterance.id == utterance_id,
        Utterance.session_id == session_id,
    ).first()
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
    db: Session = Depends(get_db)
):
    """Get utterances for an interview session, optionally filtered by section and/or speaker."""
    logger.info(f"Retrieving utterances for session {session_id}")
    utterances = interview_service.get_utterances(
        db=db,
        session_id=session_id,
        section_id=section_id,
        speaker=speaker,
        limit=limit
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
                }
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


@router.patch(
    "/{session_id}/card-states/{card_state_id}", response_model=InterviewCardStateSchema
)
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
    from app.services.insight_memo_service import insight_memo_service
    from app.services.evidence_matrix_service import evidence_matrix_service

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
    # TODO: Implement SSE or WebSocket event stream
    # For now, return placeholder
    return {
        "message": "Event stream endpoint - to be implemented",
        "sessionId": session_id,
    }


@router.get("/{session_id}/log")
async def get_session_log(session_id: str, db: Session = Depends(get_db)):
    """Get a unified chronological timeline of everything that happened in a session."""
    from app.models.utterance import Utterance
    from app.models.live_utterance import LiveUtterance
    from app.models.final_utterance import FinalUtterance
    from app.models.interview_session import InterviewSession, InterviewCardState
    from app.models.card_coverage_evaluation import CardCoverageEvaluation
    from app.models.ai_usage_event import AIUsageEvent

    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    events = []

    if session.started_at:
        events.append({"type": "session", "action": "started", "timestamp": session.started_at.isoformat()})
    if session.paused_at:
        events.append({"type": "session", "action": "paused", "timestamp": session.paused_at.isoformat()})
    if session.ended_at:
        events.append({"type": "session", "action": "ended", "timestamp": session.ended_at.isoformat()})

    # Prefer final_utterances, then live_utterances, then old utterances
    final_utts = db.query(FinalUtterance).filter(FinalUtterance.session_id == session_id).order_by(FinalUtterance.sequence_index).all()
    if final_utts:
        for u in final_utts:
            events.append({
                "type": "utterance",
                "speaker": u.speaker_display_name or u.speaker_label,
                "transcript": u.transcript,
                "timestamp": (u.started_at or u.created_at).isoformat(),
            })
    else:
        live_utts = db.query(LiveUtterance).filter(LiveUtterance.session_id == session_id, LiveUtterance.is_partial == False).order_by(LiveUtterance.created_at).all()
        if live_utts:
            for u in live_utts:
                events.append({
                    "type": "utterance",
                    "speaker": u.speaker,
                    "transcript": u.transcript,
                    "timestamp": (u.started_at or u.created_at).isoformat(),
                })
        else:
            old_utts = db.query(Utterance).filter(Utterance.session_id == session_id).order_by(Utterance.created_at).all()
            for u in old_utts:
                events.append({
                    "type": "utterance",
                    "speaker": u.speaker,
                    "transcript": u.transcript,
                    "timestamp": (u.started_at or u.created_at).isoformat(),
                })

    # Card coverage: prefer CardCoverageEvaluation, fallback to InterviewCardState
    coverage_evals = db.query(CardCoverageEvaluation).filter(CardCoverageEvaluation.session_id == session_id).order_by(CardCoverageEvaluation.created_at).all()
    if coverage_evals:
        for ce in coverage_evals:
            events.append({
                "type": "card_update",
                "cardId": ce.card_id,
                "status": ce.state,
                "basisType": ce.basis_type,
                "confidence": float(ce.confidence) if ce.confidence else None,
                "evidence": ce.evidence,
                "timestamp": ce.created_at.isoformat(),
            })
    else:
        card_states = db.query(InterviewCardState).filter(InterviewCardState.session_id == session_id).all()
        for cs in card_states:
            if cs.status != "pending":
                events.append({
                    "type": "card_update",
                    "cardId": cs.question_card_id,
                    "status": cs.status,
                    "confidence": float(cs.confidence) if cs.confidence else None,
                    "evidenceTranscript": cs.evidence_transcript,
                    "timestamp": (cs.answered_at or cs.updated_at).isoformat(),
                })

    ai_events = db.query(AIUsageEvent).filter(AIUsageEvent.interview_session_id == session_id).order_by(AIUsageEvent.created_at).all()
    for ae in ai_events:
        events.append({
            "type": "ai_usage",
            "operation": ae.operation,
            "model": ae.model,
            "totalTokens": ae.total_tokens,
            "costUsd": float(ae.cost_usd),
            "timestamp": ae.created_at.isoformat(),
        })

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
    from app.models.interview_session import InterviewSession
    from app.models.live_utterance import LiveUtterance
    from app.models.final_utterance import FinalUtterance
    from app.models.card_coverage_evaluation import CardCoverageEvaluation
    from app.models.question_instance import QuestionInstance
    from app.models.question_answer import QuestionAnswer
    from app.models.utterance_alignment import UtteranceAlignment
    from app.models.ai_usage_event import AIUsageEvent
    from app.models.question_card import QuestionCard
    from sqlalchemy import func

    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # === Transcription Stats ===
    live_count = db.query(LiveUtterance).filter(
        LiveUtterance.session_id == session_id,
        LiveUtterance.is_partial == False,
    ).count()

    final_count = db.query(FinalUtterance).filter(
        FinalUtterance.session_id == session_id
    ).count()

    speakers = db.query(func.count(func.distinct(FinalUtterance.speaker_label))).filter(
        FinalUtterance.session_id == session_id
    ).scalar() or 0

    # Alignment match rate
    total_alignments = db.query(UtteranceAlignment).filter(
        UtteranceAlignment.session_id == session_id
    ).count()

    matched_alignments = db.query(UtteranceAlignment).filter(
        UtteranceAlignment.session_id == session_id,
        UtteranceAlignment.final_utterance_id.isnot(None),
    ).count()

    alignment_rate = round(matched_alignments / total_alignments, 3) if total_alignments > 0 else None

    # === Card Coverage Stats ===
    total_cards = db.query(QuestionCard).filter(
        QuestionCard.document_id == session.document_id
    ).count() if session.document_id else 0

    def coverage_breakdown(basis_type):
        """Get latest evaluation per card for given basis type."""
        evals = db.query(CardCoverageEvaluation).filter(
            CardCoverageEvaluation.session_id == session_id,
            CardCoverageEvaluation.basis_type == basis_type,
        ).all()

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
    live_evals = db.query(CardCoverageEvaluation).filter(
        CardCoverageEvaluation.session_id == session_id,
        CardCoverageEvaluation.basis_type == "live",
    ).all()

    final_evals = db.query(CardCoverageEvaluation).filter(
        CardCoverageEvaluation.session_id == session_id,
        CardCoverageEvaluation.basis_type == "final",
    ).all()

    # Build latest eval maps
    latest_live = {}
    for e in live_evals:
        if e.card_id not in latest_live or e.evaluation_seq > latest_live[e.card_id].evaluation_seq:
            latest_live[e.card_id] = e

    latest_final = {}
    for e in final_evals:
        if e.card_id not in latest_final or e.evaluation_seq > latest_final[e.card_id].evaluation_seq:
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
    q_count = db.query(QuestionInstance).filter(
        QuestionInstance.session_id == session_id
    ).count()

    qa_statuses = db.query(
        QuestionAnswer.answer_status,
        func.count(QuestionAnswer.id)
    ).filter(
        QuestionAnswer.session_id == session_id
    ).group_by(QuestionAnswer.answer_status).all()

    qa_stats = {status: count for status, count in qa_statuses}

    card_matched = db.query(QuestionInstance).filter(
        QuestionInstance.session_id == session_id,
        QuestionInstance.card_id.isnot(None),
    ).count()

    card_match_rate = round(card_matched / q_count, 3) if q_count > 0 else None

    # === AI Usage Stats ===
    ai_events = db.query(AIUsageEvent).filter(
        AIUsageEvent.interview_session_id == session_id
    ).all()

    nano_count = sum(1 for e in ai_events if e.model and 'nano' in e.model.lower())
    mini_count = sum(1 for e in ai_events if e.model and 'mini' in e.model.lower())
    total_tokens = sum(e.total_tokens or 0 for e in ai_events)
    total_cost = sum(float(e.cost_usd) if e.cost_usd else 0 for e in ai_events)

    # === Quality Metrics ===
    # Evidence quote rate (for final sufficient cards)
    final_sufficient = db.query(CardCoverageEvaluation).filter(
        CardCoverageEvaluation.session_id == session_id,
        CardCoverageEvaluation.basis_type == "final",
        CardCoverageEvaluation.state == "sufficient",
    ).all()

    # Get latest sufficient per card
    latest_sufficient = {}
    for e in final_sufficient:
        if e.card_id not in latest_sufficient or e.evaluation_seq > latest_sufficient[e.card_id].evaluation_seq:
            latest_sufficient[e.card_id] = e

    with_evidence = sum(
        1 for e in latest_sufficient.values()
        if e.evidence and len(e.evidence) > 0
    )
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
        raise HTTPException(
            status_code=400,
            detail="Session has no stakeholder profile assigned"
        )
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
