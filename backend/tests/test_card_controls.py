from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.card_controls import clear_active_card, set_active_card
from app.models.interview_session import InterviewCardState, InterviewSession
from app.models.live_utterance import LiveUtterance


def _query_result(first_result):
    query = Mock()
    query.filter.return_value.first.return_value = first_result
    return query


@pytest.mark.asyncio
async def test_clear_active_card_clears_routing_state_and_publishes_card_id():
    session = SimpleNamespace(
        active_card_id="card-1",
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


@pytest.mark.asyncio
async def test_set_active_card_replays_buffered_answers_and_publishes_criterion_evidence():
    session = SimpleNamespace(
        id="session-1",
        current_theme_id="theme-1",
        active_card_id=None,
        active_card_source=None,
        active_card_confirmed_at=None,
        pending_answer_buffer=["utterance-1"],
    )
    card_state = SimpleNamespace(
        session_id="session-1",
        question_card_id="card-1",
        status="pending",
        activation_score=0.0,
        updated_at=None,
    )
    utterance = SimpleNamespace(
        id="utterance-1",
        transcript="有說明接單來源，也提到誰負責。",
    )

    db = Mock()

    def query_side_effect(model):
        if model is InterviewSession:
            return _query_result(session)
        if model is InterviewCardState:
            return _query_result(card_state)
        if model is LiveUtterance:
            return _query_result(utterance)
        raise AssertionError(f"Unexpected query model: {model}")

    db.query.side_effect = query_side_effect

    replay_update = {
        "card_id": "card-1",
        "old_status": "listening",
        "new_status": "probably_sufficient",
        "activation_score": 1.0,
        "completion_score": 0.72,
        "confidence": 0.72,
        "evidence": {"reason": "回答涵蓋部分條件"},
        "evidence_transcript": "有說明接單來源，也提到誰負責。",
        "evaluation_seq": 3,
        "judgment": {
            "criterion_evaluations": [
                {
                    "criterion_id": "criterion-1",
                    "status": "satisfied",
                    "evidence_quotes": ["有說明接單來源"],
                },
                {
                    "criterion_id": "criterion-2",
                    "status": "not_addressed",
                    "evidence_quotes": ["不應該被發布"],
                },
            ]
        },
    }

    with (
        patch("app.services.event_service.event_service.publish_sync") as publish_sync,
        patch(
            "app.services.answer_evaluation_engine.answer_evaluation_engine._evaluate_answer",
            return_value=[replay_update],
        ) as evaluate_answer,
    ):
        result = await set_active_card(
            "session-1",
            {"cardId": "card-1", "source": "human_confirmed_ai_suggestion"},
            db,
        )

    assert result == {
        "cardId": "card-1",
        "status": "listening",
        "activationScore": 1.0,
        "bufferedAnswersReplayed": 1,
    }
    assert session.active_card_id == "card-1"
    assert session.active_card_source == "human_confirmed_ai_suggestion"
    assert session.pending_answer_buffer is None
    assert card_state.status == "listening"
    assert card_state.activation_score == 1.0
    db.commit.assert_called_once_with()
    evaluate_answer.assert_called_once_with(
        db,
        "session-1",
        "utterance-1",
        "有說明接單來源，也提到誰負責。",
        "theme-1",
    )

    published_payloads = [call.args[1] for call in publish_sync.call_args_list]
    assert published_payloads[0]["type"] == "ACTIVE_CARD_CHANGED"
    assert {
        "type": "CARD_PROBABLY_COVERED",
        "card_id": "card-1",
        "old_status": "listening",
        "new_status": "probably_sufficient",
        "activation_score": 1.0,
        "completion_score": 0.72,
        "confidence": 0.72,
        "evidence": {"reason": "回答涵蓋部分條件"},
        "evidenceTranscript": "有說明接單來源，也提到誰負責。",
        "evaluationSeq": 3,
    } in published_payloads
    assert {
        "type": "CARD_EVIDENCE_ADDED",
        "card_id": "card-1",
        "criterion_id": "criterion-1",
        "status": "satisfied",
        "evidence_quote": "有說明接單來源",
        "completion_score": 0.72,
        "evaluationSeq": 3,
    } in published_payloads
    assert not any(
        payload.get("type") == "CARD_EVIDENCE_ADDED"
        and payload.get("criterion_id") == "criterion-2"
        for payload in published_payloads
    )
    assert published_payloads[-1] == {
        "type": "ANSWER_BUFFER_REPLAYED",
        "card_id": "card-1",
        "replayed_count": 1,
    }
