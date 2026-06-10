"""Prep session routes."""

import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import redis.asyncio as async_redis

from app.db.session import get_db
from app.services.prep_session_service import prep_session_service
from app.services.interview_service import interview_service
from app.services.billing_service import billing_service
from app.services.event_service import event_service
from app.core.config import settings
from app.schemas.prep_session import (
    PrepSessionSchema,
    PrepSessionCreate,
    PrepSessionUpdate,
    PrepSessionListResponse,
    PrepSessionWithDocument
)
from app.schemas.interview import (
    InterviewSessionSchema,
    InterviewSessionCreate,
    InterviewSessionWithDocument
)

logger = logging.getLogger(__name__)

router = APIRouter()


def convert_prep_session_to_schema(prep_session) -> PrepSessionSchema:
    """Convert prep session model to schema."""
    return PrepSessionSchema(
        id=prep_session.id,
        deckId=prep_session.document_id,
        userId=prep_session.user_id,
        title=prep_session.title,
        status=prep_session.status,
        createdAt=prep_session.created_at,
        updatedAt=prep_session.updated_at
    )


def convert_presentation_session_to_schema(session, db: Optional[Session] = None) -> InterviewSessionSchema:
    """Convert presentation session model to schema."""
    usage = billing_service.summarize_session(db, session.id) if db else billing_service.empty_summary()
    return InterviewSessionSchema(
        id=session.id,
        prepSessionId=session.prep_session_id,
        deckId=session.document_id,
        userId=session.user_id,
        status=session.status,
        currentSlideId=session.current_slide_id,
        startedAt=session.started_at,
        endedAt=session.ended_at,
        pausedAt=session.paused_at,
        pausedDurationSeconds=session.paused_duration_seconds or 0,
        createdAt=session.created_at,
        costUsd=usage["totalCostUsd"],
        aiUsage=usage
    )


@router.get("/", response_model=PrepSessionListResponse)
async def list_prep_sessions(
    status_filter: Optional[str] = Query(None, alias="status"),
    deck_id: Optional[str] = Query(None, alias="deckId"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("createdAt", alias="sortBy", regex="^(createdAt|updatedAt|status)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """
    List all prep sessions with pagination, sorting, and filtering.

    Query parameters:
    - status: Filter by prep session status (preparing, ready, archived)
    - deckId: Filter by deck ID
    - limit: Number of prep sessions to return (1-1000, default 50)
    - offset: Number of prep sessions to skip (for pagination)
    - sortBy: Field to sort by (createdAt, updatedAt, status)
    - order: Sort order (asc or desc, default desc)
    """
    logger.info(f"Listing prep sessions: status={status_filter}, deck_id={deck_id}, limit={limit}, offset={offset}")

    # For MVP, use default user
    user_id = "user_default"

    result = prep_session_service.list_prep_sessions(
        db=db,
        user_id=user_id,
        status_filter=status_filter,
        deck_id=deck_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        order=order
    )

    return result


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=PrepSessionSchema)
async def create_prep_session(
    prep_session_data: PrepSessionCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new prep session for a deck.

    This initializes a prep session that can contain multiple presentation sessions.
    """
    logger.info(f"Creating prep session for deck {prep_session_data.deckId}")

    # For MVP, use default user
    user_id = "user_default"

    prep_session = prep_session_service.create_prep_session(db, user_id, prep_session_data)

    # Publish global event for prep session creation
    try:
        event_service.publish_sync(f"prep_sessions_global", {
            'type': 'PREP_SESSION_CREATED',
            'prepSessionId': prep_session.id,
            'deckId': prep_session.document_id,
            'status': prep_session.status,
            'title': prep_session.title
        })
        logger.info(f"📤 Published PREP_SESSION_CREATED event for {prep_session.id}")
    except Exception as e:
        logger.warning(f"Failed to publish prep session created event: {e}")

    return convert_prep_session_to_schema(prep_session)




@router.get("/events")
async def prep_sessions_global_events_stream():
    """
    SSE endpoint for global prep session events.

    Events:
    - PREP_SESSION_CREATED: New prep session created
    - PREP_SESSION_DELETED: Prep session deleted
    """
    async def event_generator():
        """Generate SSE events for all prep sessions."""
        queue = await event_service.subscribe(f"prep_sessions_global")
        redis_client = async_redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(event_service.redis_channel(f"prep_sessions_global"))

        try:
            # Send initial connected event
            yield f"event: connected\ndata: {{\"status\": \"connected\"}}\n\n"

            # Stream events from queue
            while True:
                try:
                    redis_message_task = asyncio.create_task(pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=30.0
                    ))
                    local_message_task = asyncio.create_task(queue.get())

                    done, pending = await asyncio.wait(
                        {redis_message_task, local_message_task},
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=30.0,
                    )

                    for task in pending:
                        task.cancel()

                    if not done:
                        yield ": keepalive\n\n"
                        continue

                    completed_task = done.pop()
                    message = completed_task.result()

                    if isinstance(message, dict):
                        event_data = message.get("data")
                    else:
                        event_data = message

                    if event_data:
                        yield event_data if str(event_data).endswith("\n\n") else f"{event_data}\n\n"

                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                except Exception as e:
                    logger.error(f"Error in event generator: {e}")
                    break

        finally:
            await pubsub.unsubscribe(event_service.redis_channel(f"prep_sessions_global"))
            await pubsub.close()
            await redis_client.close()
            await event_service.unsubscribe(f"prep_sessions_global", queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@router.get("/{prep_session_id}", response_model=PrepSessionSchema)
async def get_prep_session(prep_session_id: str, db: Session = Depends(get_db)):
    """Get prep session by ID."""
    logger.info(f"Retrieving prep session {prep_session_id}")
    prep_session = prep_session_service.get_prep_session(db, prep_session_id)
    return convert_prep_session_to_schema(prep_session)


@router.patch("/{prep_session_id}", response_model=PrepSessionSchema)
async def update_prep_session(
    prep_session_id: str,
    update_data: PrepSessionUpdate,
    db: Session = Depends(get_db)
):
    """Update prep session title or status."""
    logger.info(f"Updating prep session {prep_session_id}")
    prep_session = prep_session_service.update_prep_session(db, prep_session_id, update_data)
    return convert_prep_session_to_schema(prep_session)


@router.post("/fix-stuck-sessions")
async def fix_stuck_prep_sessions(db: Session = Depends(get_db)):
    """
    Fix prep sessions that are stuck in 'preparing' status when their deck is already 'analyzed'.

    This endpoint automatically detects and fixes prep sessions that failed to update
    due to worker restart, errors, or missing update code in older versions.

    Returns a list of fixed prep session IDs.
    """
    from app.models.prep_session import PrepSession
    from app.models.document import Document
    from app.models.question_card import QuestionCard
    from sqlalchemy import and_
    from datetime import datetime

    logger.info("Starting stuck prep sessions repair")

    # Find all prep sessions in 'preparing' status with analyzed decks
    stuck_sessions = db.query(PrepSession, Document).join(
        Document, PrepSession.document_id == Document.id
    ).filter(
        and_(
            PrepSession.status == "preparing",
            Document.status == "analyzed"
        )
    ).all()

    if not stuck_sessions:
        logger.info("No stuck prep sessions found")
        return {"fixed": [], "count": 0}

    logger.warning(f"Found {len(stuck_sessions)} stuck prep session(s)")

    fixed_ids = []
    for prep_session, deck in stuck_sessions:
        # Count topic cards to verify analysis is complete
        card_count = db.query(QuestionCard).filter(
            QuestionCard.document_id == deck.id
        ).count()

        logger.info(
            f"Fixing PrepSession {prep_session.id}: deck={deck.id}, "
            f"cards={card_count}, deck_status={deck.status}"
        )

        prep_session.status = "ready"
        prep_session.updated_at = datetime.utcnow()

        # Publish SSE event
        try:
            event_service.publish_sync(f"prep_{prep_session.id}", {
                'type': 'PREP_STATUS_CHANGED',
                'prepSessionId': prep_session.id,
                'status': 'ready',
                'deckId': deck.id
            })
            logger.info(f"Published PREP_STATUS_CHANGED event for {prep_session.id}")
        except Exception as e:
            logger.warning(f"Failed to publish event for {prep_session.id}: {e}")

        fixed_ids.append(prep_session.id)

    db.commit()

    logger.info(f"Successfully fixed {len(fixed_ids)} prep session(s)")

    return {"fixed": fixed_ids, "count": len(fixed_ids)}


@router.delete("/all", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_prep_sessions(db: Session = Depends(get_db)):
    """
    Delete ALL prep sessions and all related data.

    WARNING: This is a destructive operation that will delete:
    - All prep sessions
    - All presentation sessions
    - All presentation card states
    - All utterances

    Use with caution!
    """
    logger.warning("Deleting ALL prep sessions - destructive operation")

    # For MVP, use default user
    user_id = "user_default"

    prep_session_service.delete_all_prep_sessions(db, user_id)
    return None


@router.delete("/{prep_session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prep_session(prep_session_id: str, db: Session = Depends(get_db)):
    """
    Delete a prep session and the associated deck.

    ⚠️ WARNING: This is a destructive operation that will delete:
    - The prep session
    - All presentation sessions (cascade)
    - The associated deck
    - All slides (cascade from deck)
    - All topic cards (cascade from deck)
    - S3 files (PPTX, PDF, slide images)

    This action cannot be undone.
    """
    logger.info(f"Deleting prep session {prep_session_id}")
    prep_session_service.delete_prep_session(db, prep_session_id)

    # Publish global event for prep session deletion
    try:
        event_service.publish_sync(f"prep_sessions_global", {
            'type': 'PREP_SESSION_DELETED',
            'prepSessionId': prep_session_id
        })
        logger.info(f"📤 Published PREP_SESSION_DELETED event for {prep_session_id}")
    except Exception as e:
        logger.warning(f"Failed to publish prep session deleted event: {e}")

    return None


@router.get("/{prep_session_id}/presentation-sessions", response_model=List[InterviewSessionSchema])
async def get_prep_session_presentation_sessions(
    prep_session_id: str,
    db: Session = Depends(get_db)
):
    """Get all presentation sessions for a prep session."""
    logger.info(f"Retrieving presentation sessions for prep session {prep_session_id}")
    sessions = prep_session_service.get_prep_session_presentation_sessions(db, prep_session_id)
    return [convert_presentation_session_to_schema(s, db) for s in sessions]


@router.post(
    "/{prep_session_id}/presentation-sessions",
    status_code=status.HTTP_201_CREATED,
    response_model=InterviewSessionSchema
)
async def create_presentation_session_for_prep(
    prep_session_id: str,
    db: Session = Depends(get_db)
):
    """
    Create a new presentation session under a prep session.

    This initializes a presentation session and creates initial card states for all topic cards.
    """
    logger.info(f"Creating presentation session for prep session {prep_session_id}")

    # For MVP, use default user
    user_id = "user_default"

    # Get prep session to get deck_id
    prep_session = prep_session_service.get_prep_session(db, prep_session_id)

    # Create session data
    session_data = InterviewSessionCreate(
        prepSessionId=prep_session_id,
        deckId=prep_session.document_id
    )

    session = interview_service.create_session(db, user_id, session_data)
    return convert_presentation_session_to_schema(session, db)


@router.get("/{prep_session_id}/events")
async def prep_session_events_stream(prep_session_id: str, db: Session = Depends(get_db)):
    """
    SSE endpoint for real-time prep session status updates.

    Events:
    - PREP_STATUS_CHANGED: Prep session status changed (preparing -> ready)
    - ANALYSIS_PROGRESS: Document analysis progress updates
    """
    # Verify prep session exists
    prep_session_service.get_prep_session(db, prep_session_id)

    async def event_generator():
        """Generate SSE events for this prep session."""
        queue = await event_service.subscribe(f"prep_{prep_session_id}")
        redis_client = async_redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(event_service.redis_channel(f"prep_{prep_session_id}"))

        try:
            # Send initial connected event
            yield f"event: connected\ndata: {{\"status\": \"connected\", \"prepSessionId\": \"{prep_session_id}\"}}\n\n"

            # Stream events from queue
            while True:
                try:
                    redis_message_task = asyncio.create_task(pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=30.0
                    ))
                    local_message_task = asyncio.create_task(queue.get())

                    done, pending = await asyncio.wait(
                        {redis_message_task, local_message_task},
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=30.0,
                    )

                    for task in pending:
                        task.cancel()

                    if not done:
                        yield ": keepalive\n\n"
                        continue

                    completed_task = done.pop()
                    message = completed_task.result()

                    if isinstance(message, dict):
                        event_data = message.get("data")
                    else:
                        event_data = message

                    if event_data:
                        yield event_data if str(event_data).endswith("\n\n") else f"{event_data}\n\n"

                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent connection timeout
                    yield ": keepalive\n\n"
                except Exception as e:
                    logger.error(f"Error in event generator: {e}")
                    break

        finally:
            await pubsub.unsubscribe(event_service.redis_channel(f"prep_{prep_session_id}"))
            await pubsub.close()
            await redis_client.close()
            await event_service.unsubscribe(f"prep_{prep_session_id}", queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        }
    )
