"""Shared helper functions for interview session routes."""

from typing import Optional

from sqlalchemy.orm import Session

from app.schemas.interview import InterviewCardStateSchema, InterviewSessionSchema, UtteranceSchema
from app.services.billing_service import billing_service
from app.services.interview_service import interview_service


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
