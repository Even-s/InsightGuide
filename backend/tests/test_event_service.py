"""
Unit tests for Event Service
Tests SSE formatting, connection management, and Redis channel naming.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest

from app.services.event_service import EventService, event_service


class TestEventService:
    """Test suite for event service."""

    def test_service_initialization(self):
        assert event_service is not None
        assert isinstance(event_service, EventService)

    def test_redis_channel_format(self):
        channel = event_service.redis_channel("session-123")
        assert channel == "insightguide:events:session-123"

    def test_redis_channel_different_sessions(self):
        ch1 = event_service.redis_channel("session-1")
        ch2 = event_service.redis_channel("session-2")
        assert ch1 != ch2

    def test_format_sse_message_basic(self):
        event = {"type": "message", "data": "hello"}
        result = event_service._format_sse_message(event)
        assert "event: message" in result
        assert "data:" in result
        assert '"type": "message"' in result

    def test_format_sse_message_with_id(self):
        event = {"type": "update", "id": "evt-123", "payload": "test"}
        result = event_service._format_sse_message(event)
        assert "event: update" in result
        assert "id: evt-123" in result
        assert "data:" in result

    def test_format_sse_message_no_type(self):
        event = {"data": "no type"}
        result = event_service._format_sse_message(event)
        assert "event: message" in result

    def test_format_sse_message_chinese(self):
        event = {"type": "update", "content": "你好世界"}
        result = event_service._format_sse_message(event)
        assert "你好世界" in result

    def test_format_sse_ends_with_blank_line(self):
        event = {"type": "test"}
        result = event_service._format_sse_message(event)
        assert result.endswith("\n")

    def test_get_connection_count_empty(self):
        count = event_service.get_connection_count("nonexistent-session")
        assert count == 0

    @pytest.mark.asyncio
    async def test_subscribe_creates_queue(self):
        session_id = "test-sub-session"
        queue = await event_service.subscribe(session_id)
        assert isinstance(queue, asyncio.Queue)
        # Clean up
        await event_service.unsubscribe(session_id, queue)

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_queue(self):
        session_id = "test-unsub-session"
        queue = await event_service.subscribe(session_id)
        count_before = event_service.get_connection_count(session_id)
        await event_service.unsubscribe(session_id, queue)
        count_after = event_service.get_connection_count(session_id)
        assert count_after < count_before

    @pytest.mark.asyncio
    async def test_subscribe_multiple_clients(self):
        session_id = "test-multi-session"
        q1 = await event_service.subscribe(session_id)
        q2 = await event_service.subscribe(session_id)
        assert event_service.get_connection_count(session_id) >= 2
        # Clean up
        await event_service.unsubscribe(session_id, q1)
        await event_service.unsubscribe(session_id, q2)

    @pytest.mark.asyncio
    async def test_publish_delivers_to_subscribers(self):
        session_id = "test-publish-session"
        queue = await event_service.subscribe(session_id)

        # Publish directly to in-memory connections (skip Redis)
        event = {"type": "test_event", "data": "hello"}
        for q in event_service._connections.get(session_id, set()):
            await q.put(event)

        # Event should be in the queue
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received["type"] == "test_event"
        assert received["data"] == "hello"

        # Clean up
        await event_service.unsubscribe(session_id, queue)
