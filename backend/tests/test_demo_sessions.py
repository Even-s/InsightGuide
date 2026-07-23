"""Contract tests for the ready-to-run demo interview flow."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.document import Document
from app.models.interview_round import InterviewRound
from app.models.interview_series import InterviewSeries
from app.models.interview_session import InterviewCardState, InterviewSession
from app.models.interview_theme import InterviewTheme
from app.models.prep_session import PrepSession
from app.models.project import Project
from app.models.question_card import QuestionCard
from app.models.stakeholder_profile import StakeholderProfile
from app.models.stakeholder_slot import StakeholderSlot
from app.services.demo_session_service import (
    DEMO_TEMPLATES,
    DemoSessionService,
    DemoTemplateNotFoundError,
)


def test_three_public_templates_have_complete_guides():
    service = DemoSessionService()

    templates = service.list_templates()

    assert [template["id"] for template in templates] == [
        "current-process",
        "pain-and-needs",
        "new-system",
    ]
    assert [template["title"] for template in templates] == [
        "現況流程探索",
        "痛點與需求探索",
        "新系統需求確認",
    ]
    assert all(template["themeCount"] == 3 for template in templates)
    assert all(template["questionCount"] == 6 for template in templates)


def test_create_demo_session_builds_one_isolated_aggregate_and_commits_once():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    service = DemoSessionService()

    result = service.create_demo_session(db, user_id="user_default", template_id="current-process")

    added = [call.args[0] for call in db.add.call_args_list]
    bulk_added = [item for call in db.add_all.call_args_list for item in call.args[0]]
    persisted = added + bulk_added

    projects = [item for item in persisted if isinstance(item, Project)]
    assert len(projects) == 1
    assert projects[0].mode == "demo"
    assert projects[0].is_ephemeral is True
    assert projects[0].template_id == "current-process"
    assert projects[0].expires_at > datetime.utcnow()

    assert len([item for item in persisted if isinstance(item, StakeholderSlot)]) == 1
    assert len([item for item in persisted if isinstance(item, StakeholderProfile)]) == 1
    assert len([item for item in persisted if isinstance(item, InterviewSeries)]) == 1
    assert len([item for item in persisted if isinstance(item, InterviewRound)]) == 1
    assert len([item for item in persisted if isinstance(item, Document)]) == 1
    assert len([item for item in persisted if isinstance(item, PrepSession)]) == 1
    assert len([item for item in persisted if isinstance(item, InterviewTheme)]) == 3
    cards = [item for item in persisted if isinstance(item, QuestionCard)]
    assert len(cards) == 6
    assert all(card.coverage_rule["rubricVersion"] == "demo-v1" for card in cards)
    assert len([item for item in persisted if isinstance(item, InterviewSession)]) == 1
    assert len([item for item in persisted if isinstance(item, InterviewCardState)]) == 6

    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()
    assert result["interviewPath"] == f"/interview/session/{result['sessionId']}"
    assert result["documentId"] != result["sessionId"]


def test_create_demo_session_rolls_back_the_whole_aggregate_on_failure():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.flush.side_effect = [None, RuntimeError("database failure")]

    with pytest.raises(RuntimeError, match="database failure"):
        DemoSessionService().create_demo_session(
            db, user_id="user_default", template_id="pain-and-needs"
        )

    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_create_demo_session_deletes_expired_demo_projects_in_same_transaction():
    expired = Project(id="proj_expired", user_id="user_default", title="Expired Demo")
    active_session = InterviewSession(
        id="session_expired",
        prep_session_id="doc_expired",
        document_id="doc_expired",
        user_id="user_default",
        project_id=expired.id,
        status="idle",
        current_theme_id="theme_expired",
        created_at=datetime.utcnow(),
    )
    db = MagicMock()
    expired_query = MagicMock()
    expired_query.filter.return_value.all.return_value = [expired]
    session_query = MagicMock()
    session_query.filter.return_value.all.return_value = [active_session]
    db.query.side_effect = [expired_query, session_query]

    DemoSessionService().create_demo_session(db, user_id="user_default", template_id="new-system")

    db.delete.assert_called_once_with(expired)
    assert active_session.current_theme_id is None
    assert db.flush.call_count >= 1
    db.commit.assert_called_once_with()


def test_unknown_template_is_rejected_before_database_writes():
    db = MagicMock()

    with pytest.raises(DemoTemplateNotFoundError):
        DemoSessionService().create_demo_session(
            db, user_id="user_default", template_id="does-not-exist"
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_demo_session_api_uses_camel_case_contract():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    response_data = {
        "templateId": "new-system",
        "projectId": "proj_demo",
        "stakeholderProfileId": "profile_demo",
        "prepSessionId": "doc_demo",
        "documentId": "doc_demo",
        "sessionId": "session_demo",
        "expiresAt": datetime(2026, 7, 24, 12, 0, 0),
        "interviewPath": "/interview/session/session_demo",
    }
    try:
        with patch(
            "app.api.routes.demo_sessions.demo_session_service.create_demo_session",
            return_value=response_data,
        ) as create:
            response = TestClient(app).post("/api/demo-sessions", json={"templateId": "new-system"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["sessionId"] == "session_demo"
    assert response.json()["documentId"] == "doc_demo"
    assert response.json()["interviewPath"] == "/interview/session/session_demo"
    create.assert_called_once_with(db, user_id="user_default", template_id="new-system")


def test_template_api_lists_public_options():
    response = TestClient(app).get("/api/demo-sessions/templates")

    assert response.status_code == 200
    assert {item["id"] for item in response.json()["templates"]} == set(DEMO_TEMPLATES)
