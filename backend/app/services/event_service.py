"""Event service for real-time updates via Server-Sent Events (SSE)."""

import logging
import json
import asyncio
from typing import Dict, Any, Set
from datetime import datetime
from collections import defaultdict
import redis
import redis.asyncio as async_redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class EventService:
    """
    Service for broadcasting real-time events to connected clients.

    Uses Server-Sent Events (SSE) for one-way server-to-client communication.
    """

    def __init__(self):
        """Initialize event service."""
        # Store active connections per session
        # session_id -> set of queues
        self._connections: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self._async_redis_client = async_redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

    def redis_channel(self, session_id: str) -> str:
        """Return the Redis pub/sub channel used for this event stream."""
        return f"insightguide:events:{session_id}"

    async def subscribe(self, session_id: str) -> asyncio.Queue:
        """
        Subscribe to events for a presentation session.

        Args:
            session_id: Presentation session ID

        Returns:
            Queue that will receive events

        Example:
            >>> queue = await event_service.subscribe(session_id)
            >>> async for event in queue:
            ...     print(f"Event: {event}")
        """
        queue = asyncio.Queue(maxsize=100)
        self._connections[session_id].add(queue)

        logger.info(
            f"Client subscribed to session {session_id} "
            f"({len(self._connections[session_id])} total)"
        )

        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        """
        Unsubscribe from events.

        Args:
            session_id: Presentation session ID
            queue: The queue to remove
        """
        if session_id in self._connections:
            self._connections[session_id].discard(queue)

            logger.info(
                f"Client unsubscribed from session {session_id} "
                f"({len(self._connections[session_id])} remaining)"
            )

            # Clean up empty session
            if not self._connections[session_id]:
                del self._connections[session_id]

    async def publish(self, session_id: str, event: Dict[str, Any]):
        """
        Publish an event to all subscribers of a session.

        Args:
            session_id: Presentation session ID
            event: Event data dict

        Example:
            >>> await event_service.publish(session_id, {
            ...     'type': 'CARD_COVERED',
            ...     'card_id': 'card_123',
            ...     'timestamp': '2026-05-25T...'
            ... })
        """
        if session_id not in self._connections:
            logger.debug(f"No subscribers for session {session_id}")
            return

        # Add timestamp if not present
        if 'timestamp' not in event:
            event['timestamp'] = datetime.utcnow().isoformat()

        # Format as SSE message
        sse_data = self._format_sse_message(event)

        try:
            await self._async_redis_client.publish(self.redis_channel(session_id), sse_data)
        except Exception as e:
            logger.warning(f"Failed to publish {event.get('type')} to Redis: {e}")

        # Send to all queues
        dead_queues = set()
        for queue in self._connections[session_id]:
            try:
                queue.put_nowait(sse_data)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for session {session_id}")
                dead_queues.add(queue)
            except Exception as e:
                logger.error(f"Error sending to queue: {str(e)}")
                dead_queues.add(queue)

        # Remove dead queues
        for queue in dead_queues:
            self._connections[session_id].discard(queue)

        logger.debug(
            f"Published {event.get('type')} to {len(self._connections[session_id])} clients"
        )

    def publish_sync(self, session_id: str, event: Dict[str, Any]):
        """
        Synchronous version of publish for non-async contexts.

        Args:
            session_id: Presentation session ID
            event: Event data dict
        """
        if 'timestamp' not in event:
            event['timestamp'] = datetime.utcnow().isoformat()

        sse_data = self._format_sse_message(event)

        try:
            self._redis_client.publish(
                self.redis_channel(session_id),
                sse_data
            )
        except Exception as e:
            logger.warning(f"Failed to publish {event.get('type')} to Redis: {e}")

        if session_id not in self._connections:
            return

        dead_queues = set()
        for queue in self._connections[session_id]:
            try:
                queue.put_nowait(sse_data)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for session {session_id}")
                dead_queues.add(queue)
            except Exception as e:
                logger.error(f"Error sending to queue: {str(e)}")
                dead_queues.add(queue)

        for queue in dead_queues:
            self._connections[session_id].discard(queue)

    def _format_sse_message(self, event: Dict[str, Any]) -> str:
        """
        Format event as SSE message.

        SSE format:
        event: EVENT_TYPE
        data: {...json...}
        id: unique_id
        (blank line)
        """
        event_type = event.get('type', 'message')
        event_id = event.get('id', '')
        data = json.dumps(event, ensure_ascii=False)

        lines = []
        if event_type:
            lines.append(f"event: {event_type}")
        if event_id:
            lines.append(f"id: {event_id}")
        lines.append(f"data: {data}")
        lines.append("")  # Blank line to end message

        return "\n".join(lines)

    # Event type helpers

    async def publish_card_covered(
        self,
        session_id: str,
        card_id: str,
        card_title: str,
        confidence: float,
        evidence: Dict[str, Any]
    ):
        """Publish CARD_COVERED event."""
        await self.publish(session_id, {
            'type': 'CARD_COVERED',
            'card_id': card_id,
            'title': card_title,
            'confidence': confidence,
            'evidence': evidence
        })

    async def publish_card_listening(
        self,
        session_id: str,
        card_id: str,
        card_title: str,
        confidence: float,
        evidence: Dict[str, Any]
    ):
        """Publish CARD_LISTENING event when user starts speaking about a topic."""
        await self.publish(session_id, {
            'type': 'CARD_LISTENING',
            'card_id': card_id,
            'title': card_title,
            'confidence': confidence,
            'evidence': evidence
        })

    async def publish_card_probably_covered(
        self,
        session_id: str,
        card_id: str,
        card_title: str,
        confidence: float
    ):
        """Publish CARD_PROBABLY_COVERED event."""
        await self.publish(session_id, {
            'type': 'CARD_PROBABLY_COVERED',
            'card_id': card_id,
            'title': card_title,
            'confidence': confidence
        })

    async def publish_card_at_risk(
        self,
        session_id: str,
        card_id: str,
        card_title: str,
        importance: str,
        time_remaining: int
    ):
        """Publish CARD_AT_RISK event."""
        await self.publish(session_id, {
            'type': 'CARD_AT_RISK',
            'card_id': card_id,
            'title': card_title,
            'importance': importance,
            'timeRemaining': time_remaining
        })

    async def publish_card_skipped(
        self,
        session_id: str,
        card_id: str,
        card_title: str,
        importance: str
    ):
        """Publish CARD_SKIPPED event."""
        await self.publish(session_id, {
            'type': 'CARD_SKIPPED',
            'card_id': card_id,
            'title': card_title,
            'importance': importance
        })

    async def publish_slide_changed(
        self,
        session_id: str,
        old_slide_id: str,
        new_slide_id: str,
        slide_number: int
    ):
        """Publish SLIDE_CHANGED event."""
        await self.publish(session_id, {
            'type': 'SLIDE_CHANGED',
            'oldSlideId': old_slide_id,
            'newSlideId': new_slide_id,
            'slideNumber': slide_number
        })

    async def publish_session_ended(
        self,
        session_id: str,
        duration: int,
        covered_count: int,
        total_count: int
    ):
        """Publish SESSION_ENDED event."""
        await self.publish(session_id, {
            'type': 'SESSION_ENDED',
            'duration': duration,
            'coveredCount': covered_count,
            'totalCount': total_count
        })

    def get_connection_count(self, session_id: str) -> int:
        """Get number of active connections for a session."""
        return len(self._connections.get(session_id, set()))


# Singleton instance
event_service = EventService()
