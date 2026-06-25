"""Session reporting and output routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.report_analytics_service import report_analytics_service
from app.services.report_export_service import report_export_service

logger = logging.getLogger(__name__)

router = APIRouter()


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
