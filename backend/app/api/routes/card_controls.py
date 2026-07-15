"""Card manual control routes."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.interview_helpers import convert_card_state_to_schema
from app.db.session import get_db
from app.schemas.interview import InterviewCardStateSchema, InterviewCardStateUpdate
from app.services.interview_service import interview_service

logger = logging.getLogger(__name__)

router = APIRouter()


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
                    "CARD_COVERED"
                    if new_status == "sufficient"
                    else (
                        "CARD_PROBABLY_COVERED"
                        if new_status == "probably_sufficient"
                        else "CARD_LISTENING"
                    )
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

    cleared_card_id = session.active_card_id
    session.active_card_id = None
    session.active_card_hint_id = None
    session.active_card_source = "cleared"
    session.active_card_confirmed_at = None
    session.pending_answer_buffer = None
    db.commit()

    event_service.publish_sync(
        session_id,
        {
            "type": "ACTIVE_CARD_CLEARED",
            "card_id": cleared_card_id,
        },
    )
    return {"ok": True, "cardId": cleared_card_id}


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
