"""Event service for real-time updates via Server-Sent Events (SSE)."""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Set

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
        self._queue_loops: Dict[asyncio.Queue, asyncio.AbstractEventLoop] = {}
        self._redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self._async_redis_client = async_redis.Redis.from_url(
            settings.REDIS_URL, decode_responses=True
        )

    def redis_channel(self, session_id: str) -> str:
        """Return the Redis pub/sub channel used for this event stream."""
        return f"insightguide:events:{session_id}"

    async def subscribe(self, session_id: str) -> asyncio.Queue:
        """
        Subscribe to events for an interview session.

        Args:
            session_id: Interview session ID

        Returns:
            Queue that will receive events

        Example:
            >>> queue = await event_service.subscribe(session_id)
            >>> async for event in queue:
            ...     print(f"Event: {event}")
        """
        queue = asyncio.Queue(maxsize=100)
        self._connections[session_id].add(queue)
        self._queue_loops[queue] = asyncio.get_running_loop()

        logger.info(
            f"Client subscribed to session {session_id} "
            f"({len(self._connections[session_id])} total)"
        )

        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        """
        Unsubscribe from events.

        Args:
            session_id: Interview session ID
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
        self._queue_loops.pop(queue, None)

    async def publish(self, session_id: str, event: Dict[str, Any]):
        """
        Publish an event to all subscribers of a session.

        Args:
            session_id: Interview session ID
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
        if "timestamp" not in event:
            event["timestamp"] = datetime.utcnow().isoformat()

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
            session_id: Interview session ID
            event: Event data dict
        """
        if "timestamp" not in event:
            event["timestamp"] = datetime.utcnow().isoformat()

        sse_data = self._format_sse_message(event)

        try:
            self._redis_client.publish(self.redis_channel(session_id), sse_data)
        except Exception as e:
            logger.warning(f"Failed to publish {event.get('type')} to Redis: {e}")

        if session_id not in self._connections:
            return

        for queue in self._connections[session_id]:
            self._put_queue_threadsafe(session_id, queue, sse_data)

    def _put_queue_threadsafe(self, session_id: str, queue: asyncio.Queue, sse_data: str) -> None:
        """Schedule an SSE queue write from sync background-task threads."""
        loop = self._queue_loops.get(queue)
        if not loop or loop.is_closed():
            self._connections[session_id].discard(queue)
            self._queue_loops.pop(queue, None)
            return

        def put_nowait() -> None:
            try:
                queue.put_nowait(sse_data)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for session {session_id}")
                self._connections[session_id].discard(queue)
                self._queue_loops.pop(queue, None)
            except Exception as e:
                logger.error(f"Error sending to queue: {str(e)}")
                self._connections[session_id].discard(queue)
                self._queue_loops.pop(queue, None)

        loop.call_soon_threadsafe(put_nowait)

    def _format_sse_message(self, event: Dict[str, Any]) -> str:
        """
        Format event as SSE message.

        SSE format:
        event: EVENT_TYPE
        data: {...json...}
        id: unique_id
        (blank line)
        """
        event_type = event.get("type", "message")
        event_id = event.get("id", "")
        data = json.dumps(event, ensure_ascii=False)

        lines = []
        if event_type:
            lines.append(f"event: {event_type}")
        if event_id:
            lines.append(f"id: {event_id}")
        lines.append(f"data: {data}")
        lines.append("")  # Blank line to end message

        return "\n".join(lines)

    def get_connection_count(self, session_id: str) -> int:
        """Get number of active connections for a session."""
        return len(self._connections.get(session_id, set()))


# Singleton instance
event_service = EventService()
