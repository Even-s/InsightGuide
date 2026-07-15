"""Event service for real-time updates via Server-Sent Events (SSE)."""

import asyncio
import json
import logging
from collections import defaultdict
from contextlib import suppress
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
        self._redis_tasks: Dict[str, asyncio.Task] = {}
        self._redis_pubsubs: Dict[str, Any] = {}

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
        await self._start_redis_listener(session_id)

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
                await self._stop_redis_listener(session_id)
        self._queue_loops.pop(queue, None)

    async def _start_redis_listener(self, session_id: str) -> None:
        """Use one Redis subscription per active session, regardless of client count."""
        if session_id in self._redis_tasks:
            return

        pubsub = self._async_redis_client.pubsub()
        try:
            await pubsub.subscribe(self.redis_channel(session_id))
        except Exception as exc:
            logger.warning("Failed to subscribe SSE session %s to Redis: %s", session_id, exc)
            with suppress(Exception):
                await pubsub.aclose()
            return

        self._redis_pubsubs[session_id] = pubsub
        self._redis_tasks[session_id] = asyncio.create_task(
            self._redis_listener(session_id, pubsub),
            name=f"sse-redis-{session_id}",
        )

    async def _stop_redis_listener(self, session_id: str) -> None:
        task = self._redis_tasks.pop(session_id, None)
        pubsub = self._redis_pubsubs.pop(session_id, None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if pubsub:
            with suppress(Exception):
                await pubsub.unsubscribe(self.redis_channel(session_id))
            with suppress(Exception):
                await pubsub.aclose()

    async def _redis_listener(self, session_id: str, pubsub: Any) -> None:
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                payload = message.get("data")
                if isinstance(payload, str):
                    self._deliver_local(session_id, payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Redis SSE listener stopped for %s: %s", session_id, exc)

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
        # Add timestamp if not present
        if "timestamp" not in event:
            event["timestamp"] = datetime.utcnow().isoformat()

        # Format as SSE message
        sse_data = self._format_sse_message(event)

        redis_delivered = 0
        try:
            redis_delivered = await self._async_redis_client.publish(
                self.redis_channel(session_id), sse_data
            )
        except Exception as e:
            logger.warning(f"Failed to publish {event.get('type')} to Redis: {e}")

        if redis_delivered and session_id in self._redis_tasks:
            return
        self._deliver_local(session_id, sse_data)

    def _deliver_local(self, session_id: str, sse_data: str) -> None:
        """Deliver once to queues in this process (Redis listener or fallback)."""
        if session_id not in self._connections:
            return
        dead_queues = set()
        for queue in tuple(self._connections[session_id]):
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

        logger.debug(f"Delivered SSE payload to {len(self._connections[session_id])} local clients")

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

        redis_delivered = 0
        try:
            redis_delivered = self._redis_client.publish(self.redis_channel(session_id), sse_data)
        except Exception as e:
            logger.warning(f"Failed to publish {event.get('type')} to Redis: {e}")

        if session_id not in self._connections:
            return
        if redis_delivered and session_id in self._redis_tasks:
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
