"""
Test session management endpoints.
"""

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch
from app.main import app
from app.api.routes import presentation_sessions as presentation_routes
from app.db.session import Base, get_db
from app.models.deck import Deck
from app.models.prep_session import PrepSession
from app.models.presentation_session import PresentationCardState, PresentationSession
from app.models.slide import Slide
from app.models.topic_card import TopicCard
from app.models.user import User
from app.models.utterance import Utterance
from app.schemas.presentation import PartialTranscriptMatchCreate, UtteranceCreate
from app.services.prep_session_service import prep_session_service


SQLALCHEMY_DATABASE_URL = "sqlite:///./test_sessions.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def create_presenting_session_fixture(db, suffix: str):
    """Create the minimal aggregate needed for a presenting session."""
    user_id = f"user_{suffix}"
    deck_id = f"deck_{suffix}"
    prep_session_id = f"prep_{suffix}"
    slide_id = f"slide_{suffix}"
    session_id = f"session_{suffix}"

    db.query(User).filter(User.id == user_id).delete()
    db.commit()

    db.add(User(
        id=user_id,
        email=f"{user_id}@example.com",
        hashed_password="test",
    ))
    db.add(Deck(
        id=deck_id,
        user_id=user_id,
        title="Presenter Latency Deck",
        source_file_url="s3://bucket/source.pptx",
        status="ready",
    ))
    db.add(Slide(
        id=slide_id,
        deck_id=deck_id,
        page_number=1,
        title="Slide 1",
    ))
    db.add(PrepSession(
        id=prep_session_id,
        deck_id=deck_id,
        user_id=user_id,
        status="ready",
    ))
    db.add(PresentationSession(
        id=session_id,
        prep_session_id=prep_session_id,
        deck_id=deck_id,
        user_id=user_id,
        status="presenting",
        current_slide_id=slide_id,
    ))
    db.commit()
    return {
        "user_id": user_id,
        "deck_id": deck_id,
        "prep_session_id": prep_session_id,
        "slide_id": slide_id,
        "session_id": session_id,
    }


def test_list_sessions_empty():
    """Test listing sessions when database is empty."""
    response = client.get("/api/presentation-sessions/")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "total" in data
    assert isinstance(data["sessions"], list)


def test_list_sessions_with_pagination():
    """Test listing sessions with pagination parameters."""
    response = client.get(
        "/api/presentation-sessions/",
        params={"limit": 10, "offset": 0, "sortBy": "createdAt", "order": "desc"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10
    assert data["offset"] == 0


def test_list_sessions_with_status_filter():
    """Test listing sessions with status filter."""
    response = client.get(
        "/api/presentation-sessions/",
        params={"status": "ended"}
    )
    assert response.status_code == 200
    data = response.json()
    for session in data["sessions"]:
        assert session["status"] == "ended"


def test_delete_nonexistent_session():
    """Test deleting a session that doesn't exist."""
    response = client.delete("/api/presentation-sessions/nonexistent_id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_utterance_saves_before_background_matching(monkeypatch):
    """Completed transcripts should return after persistence, not after card matching."""
    db = TestingSessionLocal()
    ids = {}

    def fail_if_matching_runs_inline(*args, **kwargs):
        raise AssertionError("utterance matching should run as a background task")

    try:
        ids = create_presenting_session_fixture(db, "utterance_background")
        monkeypatch.setattr(
            presentation_routes.presentation_service,
            "process_utterance_matching",
            fail_if_matching_runs_inline,
        )

        background_tasks = BackgroundTasks()
        response = await presentation_routes.create_utterance(
            ids["session_id"],
            UtteranceCreate(
                transcript="今天先看熱門股票期貨與力積電 AI 題材。",
                slideId=ids["slide_id"],
                realtimeItemId="item_final_1",
            ),
            background_tasks,
            db,
        )

        saved = db.query(Utterance).filter_by(id=response.id).one()
        assert saved.transcript == "今天先看熱門股票期貨與力積電 AI 題材。"
        assert len(background_tasks.tasks) == 1
        task = background_tasks.tasks[0]
        assert task.func.__name__ == "process_utterance_matching_background"
        assert task.args == (
            ids["session_id"],
            response.id,
            "今天先看熱門股票期貨與力積電 AI 題材。",
            ids["slide_id"],
        )
    finally:
        db.rollback()
        if ids:
            user = db.query(User).filter_by(id=ids["user_id"]).first()
            if user:
                db.delete(user)
                db.commit()
        db.close()


@pytest.mark.asyncio
async def test_partial_transcript_match_returns_before_background_matching(monkeypatch):
    """In-flight card matching should not make the frontend wait for scoring."""

    def fail_if_matching_runs_inline(*args, **kwargs):
        raise AssertionError("partial matching should run as a background task")

    monkeypatch.setattr(
        presentation_routes.presentation_service,
        "process_partial_transcript_matching",
        fail_if_matching_runs_inline,
    )

    background_tasks = BackgroundTasks()
    response = await presentation_routes.match_partial_transcript(
        "session_partial_background",
        PartialTranscriptMatchCreate(
            transcript="力積電在 Computex 主打 3D AI Foundry。",
            slideId="slide_partial_background",
            realtimeItemId="item_partial_1",
        ),
        background_tasks,
    )

    assert response == {"accepted": True}
    assert len(background_tasks.tasks) == 1
    task = background_tasks.tasks[0]
    assert task.func.__name__ == "process_partial_transcript_matching_background"
    assert task.args == (
        "session_partial_background",
        "力積電在 Computex 主打 3D AI Foundry。",
        "slide_partial_background",
    )


def test_delete_prep_session_removes_deck_cards_and_presentation_data():
    """Deleting a prep session should remove the whole uploaded deck aggregate."""
    db = TestingSessionLocal()
    suffix = "prep_delete_cascade"
    user_id = f"user_{suffix}"
    deck_id = f"deck_{suffix}"
    prep_session_id = f"prep_{suffix}"
    slide_id = f"slide_{suffix}"
    card_id = f"card_{suffix}"
    session_id = f"session_{suffix}"
    card_state_id = f"state_{suffix}"
    utterance_id = f"utterance_{suffix}"

    try:
        db.query(User).filter(User.id == user_id).delete()
        db.commit()

        db.add(User(
            id=user_id,
            email=f"{user_id}@example.com",
            hashed_password="test",
        ))
        db.add(Deck(
            id=deck_id,
            user_id=user_id,
            title="Cascade Deck",
            source_file_url="s3://bucket/source.pptx",
            pdf_file_url="s3://bucket/source.pdf",
            status="ready",
        ))
        db.add(Slide(
            id=slide_id,
            deck_id=deck_id,
            page_number=1,
            title="Slide 1",
        ))
        db.add(TopicCard(
            id=card_id,
            deck_id=deck_id,
            slide_id=slide_id,
            slide_page_number=1,
            title="交易量前三大",
            description="測試卡片",
            importance="must",
            topic_type="data",
            coverage_rule={
                "semanticAnchors": ["交易量前三大"],
                "expectedKeywords": [],
                "mustMentionFacts": [],
                "negativeSignals": [],
            },
            estimated_seconds=30,
            order_index=0,
        ))
        db.add(PrepSession(
            id=prep_session_id,
            deck_id=deck_id,
            user_id=user_id,
            status="ready",
        ))
        db.add(PresentationSession(
            id=session_id,
            prep_session_id=prep_session_id,
            deck_id=deck_id,
            user_id=user_id,
            status="ended",
            current_slide_id=slide_id,
        ))
        db.add(PresentationCardState(
            id=card_state_id,
            session_id=session_id,
            topic_card_id=card_id,
            status="covered",
            confidence=1,
        ))
        db.add(Utterance(
            id=utterance_id,
            session_id=session_id,
            slide_id=slide_id,
            transcript="台積電、聯電、華邦電。",
        ))
        db.commit()

        with patch("app.services.deck_service.s3_service.delete_file"):
            prep_session_service.delete_prep_session(db, prep_session_id)

        assert db.query(PrepSession).filter_by(id=prep_session_id).count() == 0
        assert db.query(Deck).filter_by(id=deck_id).count() == 0
        assert db.query(Slide).filter_by(id=slide_id).count() == 0
        assert db.query(TopicCard).filter_by(id=card_id).count() == 0
        assert db.query(PresentationSession).filter_by(id=session_id).count() == 0
        assert db.query(PresentationCardState).filter_by(id=card_state_id).count() == 0
        assert db.query(Utterance).filter_by(id=utterance_id).count() == 0
    finally:
        db.rollback()
        db.close()


def test_delete_all_prep_sessions_removes_associated_decks():
    """Bulk prep-session deletion should not leave decks behind."""
    db = TestingSessionLocal()
    suffix = "prep_delete_all"
    user_id = f"user_{suffix}"
    deck_ids = [f"deck_{suffix}_{index}" for index in range(2)]

    try:
        db.query(User).filter(User.id == user_id).delete()
        db.commit()

        db.add(User(
            id=user_id,
            email=f"{user_id}@example.com",
            hashed_password="test",
        ))

        for index, deck_id in enumerate(deck_ids):
            slide_id = f"slide_{suffix}_{index}"
            card_id = f"card_{suffix}_{index}"
            prep_session_id = f"prep_{suffix}_{index}"
            db.add(Deck(
                id=deck_id,
                user_id=user_id,
                title=f"Cascade Deck {index}",
                source_file_url=f"s3://bucket/source-{index}.pptx",
                status="ready",
            ))
            db.add(Slide(
                id=slide_id,
                deck_id=deck_id,
                page_number=1,
            ))
            db.add(TopicCard(
                id=card_id,
                deck_id=deck_id,
                slide_id=slide_id,
                slide_page_number=1,
                title="重點",
                description="測試卡片",
                importance="must",
                topic_type="data",
                coverage_rule={
                    "semanticAnchors": ["重點"],
                    "expectedKeywords": [],
                    "mustMentionFacts": [],
                    "negativeSignals": [],
                },
                estimated_seconds=30,
                order_index=0,
            ))
            db.add(PrepSession(
                id=prep_session_id,
                deck_id=deck_id,
                user_id=user_id,
                status="ready",
            ))

        db.commit()

        with patch("app.services.deck_service.s3_service.delete_file"):
            prep_session_service.delete_all_prep_sessions(db, user_id)

        assert db.query(PrepSession).filter(PrepSession.user_id == user_id).count() == 0
        assert db.query(Deck).filter(Deck.id.in_(deck_ids)).count() == 0
        assert db.query(Slide).filter(Slide.deck_id.in_(deck_ids)).count() == 0
        assert db.query(TopicCard).filter(TopicCard.deck_id.in_(deck_ids)).count() == 0
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
