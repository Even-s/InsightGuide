"""Utterance-related routes."""

import logging
import threading
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.routes.interview_helpers import convert_utterance_to_schema
from app.core.config import settings
from app.db.session import get_db
from app.schemas.interview import UtteranceCreate, UtteranceSchema
from app.services.evaluation.utterance_classifier import is_question_like
from app.services.interview_service import interview_service

logger = logging.getLogger(__name__)

router = APIRouter()

_EVALUATION_DEBOUNCE_SECONDS = settings.UTTERANCE_EVALUATION_DEBOUNCE_SECONDS
_EVALUATION_TIMER_LOCK = threading.Lock()
_PENDING_EVALUATION_TIMERS: dict[str, threading.Timer] = {}
_PENDING_EVALUATION_UTTERANCE_IDS: dict[str, str] = {}


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

    Realtime segments are the canonical transcript. Role splitting is
    intentionally not part of this flow.
    """

    logger.info(f"Creating utterance for session {session_id}: {utterance.transcript[:50]}...")

    try:
        utterance_obj = await run_in_threadpool(
            interview_service.create_utterance,
            db,
            session_id,
            utterance,
        )

        theme_id = utterance.themeId
        background_tasks.add_task(
            schedule_utterance_evaluation_background,
            session_id,
            utterance_obj.id,
            utterance_obj.transcript,
            theme_id,
            utterance.askedCardIds,
        )

        return convert_utterance_to_schema(utterance_obj)
    except ValueError as e:
        # Session status validation error
        logger.warning(f"Invalid session status for utterance creation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating utterance: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create utterance: {str(e)}")


def schedule_utterance_evaluation_background(
    session_id: str,
    utterance_id: str,
    transcript: str,
    theme_id: Optional[str],
    asked_card_ids: Optional[List[str]] = None,
):
    """Schedule the latest utterance evaluation for a session.

    Instead of creating one sleeping task per utterance, keep one pending timer
    per session. New utterances cancel the earlier pending timer, so evaluation
    runs once for the most recent transcript segment after the debounce window.
    """
    if _EVALUATION_DEBOUNCE_SECONDS <= 0:
        process_utterance_evaluation_background(
            session_id,
            utterance_id,
            transcript,
            theme_id,
            asked_card_ids,
            debounce_elapsed_ms=0.0,
        )
        return

    timer = threading.Timer(
        _EVALUATION_DEBOUNCE_SECONDS,
        process_utterance_evaluation_background,
        kwargs={
            "session_id": session_id,
            "utterance_id": utterance_id,
            "transcript": transcript,
            "theme_id": theme_id,
            "asked_card_ids": asked_card_ids,
            "debounce_elapsed_ms": _EVALUATION_DEBOUNCE_SECONDS * 1000,
        },
    )
    timer.daemon = True

    with _EVALUATION_TIMER_LOCK:
        previous = _PENDING_EVALUATION_TIMERS.get(session_id)
        if previous:
            previous.cancel()
        _PENDING_EVALUATION_TIMERS[session_id] = timer
        _PENDING_EVALUATION_UTTERANCE_IDS[session_id] = utterance_id

    timer.start()


def process_utterance_evaluation_background(
    session_id: str,
    utterance_id: str,
    transcript: str,
    theme_id: Optional[str],
    asked_card_ids: Optional[List[str]] = None,
    debounce_elapsed_ms: float = 0.0,
):
    """Process the latest utterance evaluation after debounce."""
    import time

    from app.db.session import SessionLocal
    from app.models.live_utterance import LiveUtterance
    from app.services.answer_evaluation_engine import answer_evaluation_engine
    from app.services.event_service import event_service

    perf_start = time.perf_counter()
    with _EVALUATION_TIMER_LOCK:
        pending_utterance_id = _PENDING_EVALUATION_UTTERANCE_IDS.get(session_id)
        if pending_utterance_id and pending_utterance_id != utterance_id:
            logger.info(
                f"Debounce: skipping evaluation for {utterance_id}, "
                f"newer pending utterance {pending_utterance_id} will handle it"
            )
            return
        if pending_utterance_id == utterance_id:
            _PENDING_EVALUATION_TIMERS.pop(session_id, None)
            _PENDING_EVALUATION_UTTERANCE_IDS.pop(session_id, None)

    db = SessionLocal()
    try:
        # Check if newer utterances arrived during debounce window
        latest_utt = (
            db.query(LiveUtterance)
            .filter(LiveUtterance.session_id == session_id)
            .order_by(LiveUtterance.sequence_index.desc())
            .first()
        )

        if latest_utt and latest_utt.id != utterance_id:
            logger.info(
                f"Debounce: skipping evaluation for {utterance_id}, "
                f"newer utterance {latest_utt.id} will handle it"
            )
            return

        if not theme_id:
            logger.warning(
                "Utterance %s has no theme_id; transcript was saved but card evaluation is skipped",
                utterance_id,
            )
            return

        # Process utterance and get card state updates
        eval_start = time.perf_counter()
        updates = answer_evaluation_engine.process_utterance(
            db=db,
            session_id=session_id,
            utterance_id=utterance_id,
            utterance_text=transcript,
            theme_id=theme_id,
            asked_card_ids=asked_card_ids,
        )
        eval_elapsed = (time.perf_counter() - eval_start) * 1000

        # If question was detected and no card was suggested, emit candidates
        if not updates and not asked_card_ids and is_question_like(transcript):
            candidates = answer_evaluation_engine.find_candidate_cards(
                db, session_id, theme_id or "", transcript, top_k=3
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
        sse_start = time.perf_counter()
        for update in updates:
            new_status = update["new_status"]
            old_status = update["old_status"]
            completion_score = update.get("completion_score", 0.0)
            activation_score = update.get("activation_score", 0.0)

            # Determine event type
            if update.get("question_suggested"):
                event_type = "QUESTION_CARD_SUGGESTED"
            elif new_status == "sufficient":
                event_type = "CARD_COVERED"
            elif new_status == "probably_sufficient":
                event_type = "CARD_PROBABLY_COVERED"
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
                    "suggestionScore": update.get("suggestion_score"),
                    "source": update.get("suggestion_source"),
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
        sse_elapsed = (time.perf_counter() - sse_start) * 1000

        # Log performance metrics
        total_elapsed = (time.perf_counter() - perf_start) * 1000
        logger.info(
            f"[PERF] Utterance evaluation: debounce={debounce_elapsed_ms:.0f}ms "
            f"eval={eval_elapsed:.0f}ms sse={sse_elapsed:.0f}ms "
            f"total={total_elapsed:.0f}ms cards_updated={len(updates)}"
        )

        # Warn on slow evaluations
        if total_elapsed > 8000:
            logger.warning(
                f"[PERF] Slow evaluation: {total_elapsed:.0f}ms for session {session_id}"
            )

    except Exception as e:
        logger.error(f"Error processing utterance evaluation: {str(e)}", exc_info=True)
    finally:
        db.close()


@router.get("/{session_id}/utterances", response_model=List[UtteranceSchema])
async def get_session_utterances(
    session_id: str,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get chronological Realtime transcript segments for an interview session."""
    logger.info(f"Retrieving utterances for session {session_id}")
    utterances = interview_service.get_utterances(db=db, session_id=session_id, limit=limit)
    return [convert_utterance_to_schema(u) for u in utterances]
