"""Utterance evaluation debounce contract tests."""

import importlib
import inspect
from unittest.mock import Mock

import pytest

from app.api.routes import utterances
from app.api.routes.interview_sessions import router as interview_sessions_router

answer_evaluation_engine_module = importlib.import_module("app.services.answer_evaluation_engine")


class FakeTimer:
    instances = []

    def __init__(self, interval, function, kwargs=None):
        self.interval = interval
        self.function = function
        self.kwargs = kwargs or {}
        self.daemon = False
        self.started = False
        self.cancelled = False
        FakeTimer.instances.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


@pytest.fixture(autouse=True)
def clear_debounce_state():
    FakeTimer.instances.clear()
    utterances._PENDING_EVALUATION_TIMERS.clear()
    utterances._PENDING_EVALUATION_UTTERANCE_IDS.clear()
    yield
    FakeTimer.instances.clear()
    utterances._PENDING_EVALUATION_TIMERS.clear()
    utterances._PENDING_EVALUATION_UTTERANCE_IDS.clear()


def test_scheduling_new_utterance_cancels_previous_pending_timer(monkeypatch):
    monkeypatch.setattr(utterances.threading, "Timer", FakeTimer)

    utterances.schedule_utterance_evaluation_background(
        "session-1",
        "utt-1",
        "第一段",
        "theme-1",
    )
    utterances.schedule_utterance_evaluation_background(
        "session-1",
        "utt-2",
        "第二段",
        "theme-1",
    )

    assert len(FakeTimer.instances) == 2
    assert FakeTimer.instances[0].cancelled is True
    assert FakeTimer.instances[1].started is True
    assert utterances._PENDING_EVALUATION_UTTERANCE_IDS["session-1"] == "utt-2"


def test_debounce_window_is_fast_and_has_no_fixed_sleep():
    """Card evaluation should debounce quickly without a fixed sleeping task."""
    assert 0.3 <= utterances._EVALUATION_DEBOUNCE_SECONDS <= 0.5

    schedule_source = inspect.getsource(utterances.schedule_utterance_evaluation_background)
    process_source = inspect.getsource(utterances.process_utterance_evaluation_background)
    combined_source = f"{schedule_source}\n{process_source}"
    assert "sleep(" not in combined_source
    assert "asyncio.sleep" not in combined_source
    assert "Timer(" in schedule_source


def test_partial_transcript_match_endpoint_is_removed():
    """Partial Realtime deltas are frontend-only suggestions, not backend state writes."""
    paths = {getattr(route, "path", "") for route in interview_sessions_router.routes}
    assert "/{session_id}/partial-transcript-match" not in paths


def test_stale_timer_does_not_open_database_session(monkeypatch):
    utterances._PENDING_EVALUATION_UTTERANCE_IDS["session-1"] = "utt-newer"

    def fail_session_local():
        raise AssertionError("stale debounce task should not open a database session")

    monkeypatch.setattr("app.db.session.SessionLocal", fail_session_local)

    utterances.process_utterance_evaluation_background(
        "session-1",
        "utt-old",
        "舊段落",
        "theme-1",
    )

    assert utterances._PENDING_EVALUATION_UTTERANCE_IDS["session-1"] == "utt-newer"


def test_missing_theme_id_saves_transcript_but_skips_card_evaluation(monkeypatch):
    """No themeId means no card routing; do not fallback to the first theme."""
    latest_utterance = Mock(id="utt-1")
    query = Mock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.first.return_value = latest_utterance
    db = Mock()
    db.query.return_value = query
    db.close = Mock()

    monkeypatch.setattr("app.db.session.SessionLocal", lambda: db)

    process_mock = Mock()
    monkeypatch.setattr(
        answer_evaluation_engine_module.answer_evaluation_engine,
        "process_utterance",
        process_mock,
    )

    utterances.process_utterance_evaluation_background(
        "session-1",
        "utt-1",
        "這一段也必須保留在完整逐字稿。",
        None,
    )

    process_mock.assert_not_called()
    assert db.query.call_count == 1
    db.close.assert_called_once()
