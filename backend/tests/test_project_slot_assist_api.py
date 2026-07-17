"""API tests for stakeholder and interview-guide voice-assisted drafts."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_database():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        SimpleNamespace(role_label="門診行政主管")
    ]
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


@pytest.fixture
def role_draft():
    return {
        "role_category": "operations",
        "role_label": "門診掛號櫃台人員",
        "rationale": "了解每日掛號流程與常見例外。",
        "expected_contributions": ["每日掛號流程", "常見例外", "現場限制"],
        "key_questions_to_cover": [
            "最近一次遇到掛號尖峰時，哪個步驟最容易塞車？",
            "上次處理重複掛號時，你怎麼確認資料？",
        ],
        "priority": "required",
        "min_interviews": 2,
        "first_wave": True,
    }


def test_refine_role_draft_returns_unsaved_structured_content(role_draft):
    project = SimpleNamespace(id="proj_test", title="掛號系統", description="", brd_scope={})
    with (
        patch("app.api.routes.projects.project_service.get_project", return_value=project),
        patch(
            "app.api.routes.projects.stakeholder_plan_service.assist_slot_draft",
            return_value=role_draft,
        ) as assist,
    ):
        response = client.post(
            "/api/projects/proj_test/stakeholder-slot-draft/refine",
            json={
                "role_category": "operations",
                "role_label": "櫃台人員",
                "rationale": "",
                "expected_contributions": [],
                "key_questions_to_cover": [],
                "priority": "required",
                "min_interviews": 2,
                "first_wave": True,
            },
        )

    assert response.status_code == 200
    assert response.json() == {"transcript": None, "draft": role_draft}
    assert assist.call_args.kwargs["current_draft"]["role_label"] == "櫃台人員"
    assert assist.call_args.kwargs["existing_role_labels"] == ["門診行政主管"]


def test_voice_role_draft_transcribes_then_parses(role_draft):
    project = SimpleNamespace(id="proj_test", title="掛號系統", description="", brd_scope={})
    transcript = "我想加入掛號櫃台人員，了解現場流程和常見例外。"
    with (
        patch("app.api.routes.projects.project_service.get_project", return_value=project),
        patch(
            "app.services.openai_service.openai_service.client.audio.transcriptions.create",
            return_value=SimpleNamespace(text=transcript),
        ) as transcribe,
        patch(
            "app.api.routes.projects.stakeholder_plan_service.assist_slot_draft",
            return_value=role_draft,
        ) as assist,
    ):
        response = client.post(
            "/api/projects/proj_test/stakeholder-slot-draft/voice",
            files={"audio": ("role.webm", b"a" * 1500, "audio/webm")},
        )

    assert response.status_code == 200
    expected_transcript = "我想加入掛號櫃檯人員，了解現場流程和常見例外。"
    assert response.json() == {"transcript": expected_transcript, "draft": role_draft}
    assert transcribe.call_args.kwargs["model"] == "gpt-4o-transcribe"
    assert assist.call_args.kwargs["transcript"] == expected_transcript


def test_project_voice_fields_normalizes_transcript_and_ai_result_to_traditional_chinese():
    simplified_transcript = "线上预约与当日挂号系统，协助柜台人员处理资料。"
    simplified_result = {
        "title": "线上预约挂号系统",
        "description": "协助柜台人员处理线上预约和当日挂号资料。",
        "business_domain": "医疗挂号",
        "key_objectives": ["确认预约流程", "整理柜台痛点"],
        "out_of_scope": ["线上付款"],
    }

    with (
        patch(
            "app.services.openai_service.openai_service.client.audio.transcriptions.create",
            return_value=SimpleNamespace(text=simplified_transcript),
        ),
        patch(
            "app.services.openai_service.openai_service.chat_completion",
            return_value=simplified_result,
        ),
    ):
        response = client.post(
            "/api/projects/voice-to-project-fields",
            files={"audio": ("project.webm", b"a" * 1500, "audio/webm")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["transcript"] == "線上預約與當日掛號系統，協助櫃檯人員處理資料。"
    assert data["parsed"]["title"] == "線上預約掛號系統"
    assert data["parsed"]["description"] == "協助櫃檯人員處理線上預約和當日掛號資料。"
    assert data["parsed"]["business_domain"] == "醫療掛號"
    assert data["parsed"]["key_objectives"] == ["確認預約流程", "整理櫃檯痛點"]
    assert data["parsed"]["out_of_scope"] == ["線上付款"]


def test_voice_profile_draft_transcribes_and_uses_slot_context(mock_database):
    project = SimpleNamespace(id="proj_test", title="掛號系統", description="", brd_scope={})
    slot = SimpleNamespace(
        role_category="operations",
        role_label="掛號櫃台人員",
        rationale="了解現場掛號流程。",
    )
    mock_database.query.return_value.filter.return_value.first.return_value = slot
    transcript = "王小明是門診櫃台組長，熟悉掛號流程，但不熟系統架構。"
    profile_draft = {
        "name": "王小明",
        "role_title": "門診櫃台組長",
        "department": "",
        "stakeholder_type": "operations",
        "expertise_tags": ["掛號流程"],
        "knowledge_boundaries": ["系統架構"],
    }

    with (
        patch("app.api.routes.projects.project_service.get_project", return_value=project),
        patch(
            "app.services.openai_service.openai_service.client.audio.transcriptions.create",
            return_value=SimpleNamespace(text=transcript),
        ) as transcribe,
        patch(
            "app.api.routes.projects.stakeholder_plan_service.assist_profile_draft",
            return_value=profile_draft,
        ) as assist,
    ):
        response = client.post(
            "/api/projects/proj_test/stakeholder-profile-draft/voice?slot_id=slot_ops",
            files={"audio": ("profile.webm", b"a" * 1500, "audio/webm")},
        )

    assert response.status_code == 200
    expected_transcript = "王小明是門診櫃檯組長，熟悉掛號流程，但不熟系統架構。"
    assert response.json() == {"transcript": expected_transcript, "draft": profile_draft}
    assert transcribe.call_args.kwargs["model"] == "gpt-4o-transcribe"
    assert assist.call_args.kwargs["transcript"] == expected_transcript
    assert assist.call_args.kwargs["slot_context"]["role_label"] == "掛號櫃台人員"


def test_voice_interview_guide_draft_preserves_current_options(mock_database):
    project = SimpleNamespace(id="proj_test", title="掛號系統", description="", brd_scope={})
    profile = SimpleNamespace(
        id="profile_1",
        project_id="proj_test",
        slot_assignments=[SimpleNamespace(slot_id="slot_ops")],
        name="王小明",
        role_title="門診櫃台組長",
        department="門診行政部",
        stakeholder_type="operations",
        expertise_tags=["掛號流程"],
        knowledge_boundaries=["系統架構"],
    )
    slot = SimpleNamespace(
        role_category="operations",
        role_label="掛號櫃台人員",
        rationale="了解現場掛號流程。",
    )
    mock_database.query.return_value.filter.return_value.first.side_effect = [profile]
    mock_database.query.return_value.filter.return_value.all.return_value = [slot]
    current = {
        "duration_minutes": 30,
        "interview_purpose": "了解現有掛號流程",
        "focus_topics": "每日作業",
        "exclude_topics": "",
        "interview_style": "structured",
    }
    draft = {
        **current,
        "duration_minutes": 45,
        "exclude_topics": "系統架構",
    }
    transcript = "改成四十五分鐘，不要問系統架構。"

    with (
        patch("app.api.routes.projects.project_service.get_project", return_value=project),
        patch(
            "app.services.openai_service.openai_service.client.audio.transcriptions.create",
            return_value=SimpleNamespace(text=transcript),
        ),
        patch(
            "app.api.routes.projects.stakeholder_plan_service.assist_interview_guide_draft",
            return_value=draft,
        ) as assist,
    ):
        response = client.post(
            "/api/projects/proj_test/stakeholders/profile_1/interview-guide-draft/voice",
            files={"audio": ("guide.webm", b"a" * 1500, "audio/webm")},
            data={"current_options": json.dumps(current)},
        )

    assert response.status_code == 200
    assert response.json() == {"transcript": transcript, "draft": draft}
    assert assist.call_args.kwargs["current_draft"] == current
    assert assist.call_args.kwargs["profile_context"]["name"] == "王小明"
    assert (
        assist.call_args.kwargs["profile_context"]["slot"]["roles"][0]["role_label"]
        == "掛號櫃台人員"
    )


def test_refine_role_draft_requires_role_name():
    project = SimpleNamespace(id="proj_test", title="掛號系統", description="", brd_scope={})
    with patch("app.api.routes.projects.project_service.get_project", return_value=project):
        response = client.post(
            "/api/projects/proj_test/stakeholder-slot-draft/refine",
            json={"role_label": ""},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "請先填寫角色名稱，再使用 AI 優化。"
