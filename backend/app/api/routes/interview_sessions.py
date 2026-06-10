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
    """Convert utterance model to schema."""
    return UtteranceSchema(
        id=utterance.id,
        sessionId=utterance.session_id,
        sectionId=utterance.section_id,
        speaker=utterance.speaker,
        transcript=utterance.transcript,
        startedAt=utterance.started_at,
        endedAt=utterance.ended_at,
        realtimeItemId=utterance.realtime_item_id,
        createdAt=utterance.created_at,
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
    db: Session = Depends(get_db),
):
    """
    List all interview sessions with pagination.

    Query parameters:
    - limit: Number of sessions to return (1-1000, default 50)
    - offset: Number of sessions to skip (for pagination)
    """
    logger.info(f"Listing interview sessions: limit={limit}, offset={offset}")

    # For MVP, use default user
    user_id = "user_default"

    result = interview_service.list_sessions(
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset,
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
async def get_interview_session(session_id: str, db: Session = Depends(get_db)):
    """Get interview session by ID."""
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
    """
    # Auto-classify speaker using rule-based heuristics (instant, no API call)
    from app.services.openai_service import openai_service
    utterance.speaker = openai_service.classify_speaker(utterance.transcript)

    logger.info(f"Creating utterance for session {session_id} (speaker: {utterance.speaker}): {utterance.transcript[:50]}...")

    try:
        utterance_obj = await run_in_threadpool(
            interview_service.create_utterance,
            db,
            session_id,
            utterance,
        )

        theme_id = utterance.themeId or utterance_obj.section_id
        # Process both speakers: interviewee for full evaluation,
        # interviewer for small progress bump (question was asked)
        if utterance.speaker in ("interviewee", "interviewer"):
            background_tasks.add_task(
                process_utterance_evaluation_background,
                session_id,
                utterance_obj.id,
                utterance_obj.transcript,
                theme_id,
                utterance_obj.speaker,
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
            logger.warning(f"Utterance {utterance_id} has no section_id, skipping evaluation")
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
                }
            )

    except Exception as e:
        logger.error(f"Error processing utterance evaluation: {str(e)}", exc_info=True)
    finally:
        db.close()


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

    # Only process interviewee responses
    if partial.speaker != "interviewee":
        return {"accepted": False, "reason": "only interviewee responses are evaluated"}

    theme_id = partial.themeId or partial.sectionId
    background_tasks.add_task(
        process_partial_transcript_evaluation_background,
        session_id,
        transcript,
        theme_id,
        partial.speaker,
    )
    return {"accepted": True}


def process_partial_transcript_evaluation_background(
    session_id: str,
    transcript: str,
    section_id: Optional[str],
    speaker: str,
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
async def end_interview_session(session_id: str, db: Session = Depends(get_db)):
    """
    End an interview session.

    This marks the session as ended and can trigger report generation.
    """
    logger.info(f"Ending interview session {session_id}")
    update_data = InterviewSessionUpdate(status="ended")
    session = interview_service.update_session(db, session_id, update_data)

    # TODO (Future): Trigger BRD generation

    return convert_session_to_schema(session, db)


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
