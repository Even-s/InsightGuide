"""Interview topic series and repeated-round API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.interview_helpers import convert_session_to_schema
from app.db.session import get_db
from app.models.interview_round import InterviewRound
from app.models.interview_round_slot import InterviewRoundSlot
from app.models.prep_session import PrepSession
from app.models.question_card import QuestionCard
from app.schemas.interview import InterviewSessionCreate, InterviewSessionSchema
from app.schemas.interview_round import (
    InterviewRoundAggregateResponse,
    InterviewRoundCreate,
    InterviewRoundGuideOptions,
    InterviewRoundGuideResponse,
    InterviewRoundResponse,
    InterviewRoundSessionCreate,
    InterviewSeriesCreate,
    InterviewSeriesResponse,
)
from app.services.interview_round_aggregate_service import interview_round_aggregate_service
from app.services.interview_round_service import interview_round_service
from app.services.interview_series_service import interview_series_service
from app.services.interview_service import interview_service

router = APIRouter()


def _series_response(series) -> InterviewSeriesResponse:
    return InterviewSeriesResponse(
        id=series.id,
        projectId=series.project_id,
        stakeholderProfileId=series.stakeholder_profile_id,
        title=series.title,
        topicKey=series.topic_key,
        status=series.status,
        roundsCount=len(series.rounds),
        createdAt=series.created_at,
        updatedAt=series.updated_at,
    )


def _round_response(db: Session, interview_round: InterviewRound) -> InterviewRoundResponse:
    card_count = 0
    guide_version = None
    if interview_round.guide_document_id:
        card_count = (
            db.query(QuestionCard)
            .filter(QuestionCard.document_id == interview_round.guide_document_id)
            .count()
        )
        if interview_round.guide_document:
            guide_version = interview_round.guide_document.guide_version
    session_ids = [session.id for session in interview_round.interview_sessions]
    target_slot_ids = [
        row.slot_id
        for row in db.query(InterviewRoundSlot)
        .filter(InterviewRoundSlot.round_id == interview_round.id)
        .all()
    ]
    aggregate = interview_round.aggregate
    return InterviewRoundResponse(
        id=interview_round.id,
        seriesId=interview_round.series_id,
        roundNumber=interview_round.round_number,
        objective=interview_round.objective,
        generationMode=interview_round.generation_mode,
        sourceSessionIds=interview_round.source_session_ids or [],
        focusTopics=interview_round.focus_topics or [],
        targetSlotIds=target_slot_ids,
        excludeCompletedQuestions=interview_round.exclude_completed_questions,
        guideDocumentId=interview_round.guide_document_id,
        guideVersion=guide_version,
        cardCount=card_count,
        status=interview_round.status,
        sessionIds=session_ids,
        aggregate=(
            InterviewRoundAggregateResponse(
                latestMemoId=aggregate.latest_memo_id,
                sourceSessionIds=aggregate.source_session_ids or [],
                coverageSnapshot=aggregate.coverage_snapshot or {},
                evidenceSnapshot=aggregate.evidence_snapshot or [],
                status=aggregate.status,
                version=aggregate.version,
                generatedAt=aggregate.generated_at,
                invalidatedAt=aggregate.invalidated_at,
            )
            if aggregate
            else None
        ),
        createdAt=interview_round.created_at,
        updatedAt=interview_round.updated_at,
    )


@router.get(
    "/projects/{project_id}/stakeholders/{profile_id}/interview-series",
    response_model=list[InterviewSeriesResponse],
)
def list_interview_series(project_id: str, profile_id: str, db: Session = Depends(get_db)):
    return [
        _series_response(series)
        for series in interview_series_service.list_series(db, project_id, profile_id)
    ]


@router.post(
    "/projects/{project_id}/stakeholders/{profile_id}/interview-series",
    response_model=InterviewSeriesResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_interview_series(
    project_id: str,
    profile_id: str,
    payload: InterviewSeriesCreate,
    db: Session = Depends(get_db),
):
    try:
        series = interview_series_service.create_series(
            db,
            project_id=project_id,
            stakeholder_profile_id=profile_id,
            title=payload.title,
            topic_key=payload.topicKey,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _series_response(series)


@router.get("/interview-series/{series_id}/rounds", response_model=list[InterviewRoundResponse])
def list_interview_rounds(series_id: str, db: Session = Depends(get_db)):
    try:
        rounds = interview_round_service.list_rounds(db, series_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_round_response(db, interview_round) for interview_round in rounds]


@router.post(
    "/interview-series/{series_id}/rounds",
    response_model=InterviewRoundResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_interview_round(
    series_id: str, payload: InterviewRoundCreate, db: Session = Depends(get_db)
):
    try:
        interview_round = interview_round_service.create_round(
            db,
            series_id,
            objective=payload.objective,
            generation_mode=payload.generationMode,
            source_session_ids=payload.sourceSessionIds,
            focus_topics=payload.focusTopics,
            target_slot_ids=payload.targetSlotIds,
            exclude_completed_questions=payload.excludeCompletedQuestions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _round_response(db, interview_round)


@router.get("/interview-rounds/{round_id}", response_model=InterviewRoundResponse)
def get_interview_round(round_id: str, db: Session = Depends(get_db)):
    try:
        interview_round = interview_round_service.get_round(db, round_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _round_response(db, interview_round)


@router.post(
    "/interview-rounds/{round_id}/aggregate/rebuild",
    response_model=InterviewRoundAggregateResponse,
)
def rebuild_interview_round_aggregate(round_id: str, db: Session = Depends(get_db)):
    try:
        aggregate = interview_round_aggregate_service.rebuild(db, round_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InterviewRoundAggregateResponse(
        latestMemoId=aggregate.latest_memo_id,
        sourceSessionIds=aggregate.source_session_ids or [],
        coverageSnapshot=aggregate.coverage_snapshot or {},
        evidenceSnapshot=aggregate.evidence_snapshot or [],
        status=aggregate.status,
        version=aggregate.version,
        generatedAt=aggregate.generated_at,
        invalidatedAt=aggregate.invalidated_at,
    )


@router.post(
    "/interview-rounds/{round_id}/generate-guide",
    response_model=InterviewRoundGuideResponse,
)
def generate_interview_round_guide(
    round_id: str,
    payload: InterviewRoundGuideOptions,
    db: Session = Depends(get_db),
):
    options = {
        "duration_minutes": payload.durationMinutes,
        "interview_style": payload.interviewStyle,
        "exclude_topics": payload.excludeTopics,
    }
    try:
        result = interview_round_service.generate_round_guide(db, round_id, options=options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InterviewRoundGuideResponse(
        documentId=result["document_id"],
        prepSessionId=result["prep_session_id"],
        seriesId=result["series_id"],
        roundId=result["round_id"],
        roundNumber=result["round_number"],
        cardCount=result["card_count"],
        status=result["status"],
        themes=result["themes"],
    )


@router.post(
    "/interview-rounds/{round_id}/sessions",
    response_model=InterviewSessionSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_interview_round_session(
    round_id: str,
    payload: Optional[InterviewRoundSessionCreate] = None,
    db: Session = Depends(get_db),
):
    try:
        interview_round = interview_round_service.get_round(db, round_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not interview_round.guide_document_id:
        raise HTTPException(status_code=400, detail="Generate the round guide before starting")

    prep_session = (
        db.query(PrepSession)
        .filter(PrepSession.document_id == interview_round.guide_document_id)
        .first()
    )
    if not prep_session or prep_session.status != "ready":
        raise HTTPException(status_code=400, detail="Interview round guide is not ready")

    series = interview_series_service.get_series(db, interview_round.series_id)
    session = interview_service.create_session(
        db,
        prep_session.user_id,
        InterviewSessionCreate(
            prepSessionId=prep_session.id,
            documentId=interview_round.guide_document_id,
            projectId=series.project_id,
            stakeholderProfileId=series.stakeholder_profile_id,
            interviewRoundId=interview_round.id,
            continueFromSessionId=(payload.continueFromSessionId if payload else None),
        ),
    )
    return convert_session_to_schema(session, db)
