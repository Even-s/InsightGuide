"""Tests for presentation timer pause accounting."""

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.presentation_service as presentation_service_module
from app.db.session import Base
from app.models.deck import Deck  # noqa: F401
from app.models.prep_session import PrepSession  # noqa: F401
from app.models.presentation_session import PresentationSession
from app.models.user import User  # noqa: F401
from app.schemas.presentation import PresentationSessionUpdate
from app.services.presentation_service import PresentationService


def make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


class FrozenDateTime(datetime):
    current = datetime(2026, 6, 2, 12, 0, 0)

    @classmethod
    def utcnow(cls):
        return cls.current


def test_pause_duration_is_excluded_from_active_timer(monkeypatch):
    monkeypatch.setattr(presentation_service_module, "datetime", FrozenDateTime)

    db = make_db()
    service = PresentationService()
    session = PresentationSession(
        id="session_timer",
        prep_session_id="prep_timer",
        deck_id="deck_timer",
        user_id="user_default",
        status="idle",
        created_at=FrozenDateTime.utcnow(),
    )
    db.add(session)
    db.commit()

    service.update_session(db, "session_timer", PresentationSessionUpdate(status="presenting"))

    FrozenDateTime.current += timedelta(seconds=10)
    paused = service.update_session(db, "session_timer", PresentationSessionUpdate(status="paused"))

    assert paused.paused_at == FrozenDateTime.current
    assert service.calculate_active_duration(paused) == 10

    FrozenDateTime.current += timedelta(seconds=60)
    resumed = service.update_session(db, "session_timer", PresentationSessionUpdate(status="presenting"))

    assert resumed.paused_at is None
    assert resumed.paused_duration_seconds == 60
    assert service.calculate_active_duration(resumed) == 10

    FrozenDateTime.current += timedelta(seconds=5)
    ended = service.end_session(db, "session_timer")

    assert ended.paused_duration_seconds == 60
    assert service.calculate_active_duration(ended, ended.ended_at) == 15
