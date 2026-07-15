from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.card_controls import clear_active_card


@pytest.mark.asyncio
async def test_clear_active_card_clears_routing_state_and_publishes_card_id():
    session = SimpleNamespace(
        active_card_id="card-1",
        active_card_hint_id="card-1",
        active_card_source="user_confirmed",
        active_card_confirmed_at="timestamp",
        pending_answer_buffer=["utterance-1"],
    )
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = session

    with patch("app.services.event_service.event_service.publish_sync") as publish_sync:
        result = await clear_active_card("session-1", db)

    assert result == {"ok": True, "cardId": "card-1"}
    assert session.active_card_id is None
    assert session.active_card_hint_id is None
    assert session.active_card_source == "cleared"
    assert session.active_card_confirmed_at is None
    assert session.pending_answer_buffer is None
    db.commit.assert_called_once_with()
    publish_sync.assert_called_once_with(
        "session-1",
        {"type": "ACTIVE_CARD_CLEARED", "card_id": "card-1"},
    )


@pytest.mark.asyncio
async def test_clear_active_card_returns_404_for_unknown_session():
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await clear_active_card("missing-session", db)

    assert exc_info.value.status_code == 404
    db.commit.assert_not_called()
