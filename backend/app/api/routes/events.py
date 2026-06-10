"""Server-Sent Events (SSE) routes for real-time updates."""

import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.event_service import event_service
from app.models.interview_session import InterviewSession
from app.models.document import Document

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/sessions/{session_id}/stream")
async def stream_session_events(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Subscribe to real-time events for an interview session via SSE.

    Events include:
    - QUESTION_ANSWERED: Question card marked as answered
    - QUESTION_PARTIALLY_ANSWERED: Question card partially answered
    - QUESTION_AT_RISK: Important question at risk of being skipped
    - QUESTION_SKIPPED: Question was skipped
    - SECTION_CHANGED: Section transition
    - SESSION_ENDED: Interview ended

    Usage (JavaScript):
    ```javascript
    const eventSource = new EventSource('/api/events/sessions/session_123/stream');

    eventSource.addEventListener('QUESTION_ANSWERED', (e) => {
      const data = JSON.parse(e.data);
      console.log('Question answered:', data.question_id);
    });

    eventSource.addEventListener('QUESTION_AT_RISK', (e) => {
      const data = JSON.parse(e.data);
      console.warn('Question at risk:', data.question_id);
    });
    ```

    Returns:
        StreamingResponse with Server-Sent Events
    """
    logger.info(f"SSE stream requested for session {session_id}")

    # Verify session or document exists (deck analysis uses document_id as session key)
    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id
    ).first()

    if not session:
        document = db.query(Document).filter(
            Document.id == session_id
        ).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

    async def event_generator():
        """Generate SSE events."""
        queue = await event_service.subscribe(session_id)

        try:
            # Send initial connection confirmation
            yield f"event: connected\ndata: {{\"sessionId\": \"{session_id}\"}}\n\n"

            # Send heartbeat every 30 seconds to keep connection alive
            heartbeat_task = asyncio.create_task(send_heartbeats(queue))

            # Stream events
            while True:
                try:
                    # Wait for event with timeout
                    event_data = await asyncio.wait_for(queue.get(), timeout=60.0)
                    yield event_data + "\n"

                except asyncio.TimeoutError:
                    # No events for 60 seconds, send comment to keep alive
                    yield ": keepalive\n\n"
                    continue

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in event generator: {str(e)}")
        finally:
            # Clean up
            heartbeat_task.cancel()
            await event_service.unsubscribe(session_id, queue)
            logger.info(f"SSE stream closed for session {session_id}")

    async def send_heartbeats(queue: asyncio.Queue):
        """Send heartbeat messages every 30 seconds."""
        try:
            while True:
                await asyncio.sleep(30)
                # SSE comment line (keeps connection alive)
                await queue.put(": heartbeat\n\n")
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Connection": "keep-alive"
        }
    )


@router.get("/sessions/{session_id}/connections")
async def get_connection_count(session_id: str):
    """
    Get number of active SSE connections for a session.

    Useful for monitoring and debugging.

    Returns:
        Dict with connection count
    """
    count = event_service.get_connection_count(session_id)

    return {
        "sessionId": session_id,
        "activeConnections": count
    }


@router.post("/sessions/{session_id}/test-event")
async def send_test_event(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Send a test event to all subscribers (for testing).

    Only available in development mode.
    """
    from app.core.config import settings

    if settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoint only available in development"
        )

    await event_service.publish(session_id, {
        'type': 'TEST_EVENT',
        'message': 'This is a test event',
        'timestamp': '2026-05-25T...'
    })

    return {
        "message": "Test event sent",
        "sessionId": session_id,
        "subscribers": event_service.get_connection_count(session_id)
    }
