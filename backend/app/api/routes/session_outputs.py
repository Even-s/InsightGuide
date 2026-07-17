"""Session event and interview helper routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{session_id}/log")
async def get_session_log(session_id: str, db: Session = Depends(get_db)):
    """Get a unified chronological timeline of everything that happened in a session."""
    from app.models.ai_usage_event import AIUsageEvent
    from app.models.card_coverage_evaluation import CardCoverageEvaluation
    from app.models.interview_session import InterviewSession
    from app.models.live_utterance import LiveUtterance

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

    live_utts = (
        db.query(LiveUtterance)
        .filter(LiveUtterance.session_id == session_id)
        .order_by(LiveUtterance.sequence_index)
        .all()
    )
    for u in live_utts:
        events.append(
            {
                "type": "utterance",
                "transcript": u.transcript,
                "timestamp": (u.started_at or u.created_at).isoformat(),
            }
        )

    # Card coverage events come only from Realtime evaluations. Clean-break
    # history does not backfill old card states into the event log.
    coverage_evals = (
        db.query(CardCoverageEvaluation)
        .filter(CardCoverageEvaluation.session_id == session_id)
        .order_by(CardCoverageEvaluation.created_at)
        .all()
    )
    for ce in coverage_evals:
        events.append(
            {
                "type": "card_update",
                "cardId": ce.card_id,
                "status": ce.state,
                "confidence": float(ce.confidence) if ce.confidence else None,
                "evidence": ce.evidence,
                "timestamp": ce.created_at.isoformat(),
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
