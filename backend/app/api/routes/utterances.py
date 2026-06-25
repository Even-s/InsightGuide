"""Utterance-related routes."""

import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.routes.interview_helpers import convert_utterance_to_schema
from app.db.session import get_db
from app.schemas.interview import PartialTranscriptMatchCreate, UtteranceCreate, UtteranceSchema
from app.services.interview_service import interview_service

logger = logging.getLogger(__name__)

router = APIRouter()

_EVALUATION_DEBOUNCE_SECONDS = 1.5


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
