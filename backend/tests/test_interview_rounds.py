"""Regression coverage for immutable multi-round interview guides."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.question_cards import _ensure_document_editable
from app.models.document import Document
from app.models.interview_insight_memo import InterviewInsightMemo
from app.models.interview_round import InterviewRound
from app.models.project import Project
from app.models.stakeholder_profile import StakeholderProfile
from app.services.interview_round_service import InterviewRoundService
from app.services.interview_series_service import InterviewSeriesService
from app.services.stakeholder_card_generator import StakeholderCardGenerator


def _project() -> Project:
    return Project(id="project-1", user_id="user-1", title="掛號系統")


def _profile() -> StakeholderProfile:
    return StakeholderProfile(
        id="profile-1",
        project_id="project-1",
        name="王小明",
        stakeholder_type="operations",
        expertise_tags=[],
        knowledge_boundaries=[],
    )


def test_frozen_guide_rejects_regeneration_without_deleting_history():
    generator = StakeholderCardGenerator()
    db = Mock()
    project = _project()
    profile = _profile()
    document = Document(
        id="doc-history",
        user_id="user-1",
        project_id="project-1",
        stakeholder_profile_id="profile-1",
        title="第一輪",
        source_file_url="generated",
        file_type="generated",
        status="analyzed",
        is_frozen=True,
    )

    project_query = Mock()
    project_query.filter.return_value.first.return_value = project
    profile_query = Mock()
    profile_query.filter.return_value.first.return_value = profile
    session_query = Mock()
    session_query.filter.return_value.first.return_value = object()

    def query_side_effect(entity):
        if entity is Project:
            return project_query
        if entity is StakeholderProfile:
            return profile_query
        return session_query

    db.query.side_effect = query_side_effect
    with patch.object(generator, "_get_or_create_round_document", return_value=document):
        with pytest.raises(ValueError, match="immutable"):
            generator.generate_cards_for_stakeholder(
                db,
                project.id,
                profile.id,
                interview_round=InterviewRound(id="round-1", series_id="series-1", round_number=1),
            )

    db.delete.assert_not_called()


def test_each_new_round_gets_a_distinct_document():
    generator = StakeholderCardGenerator()
    db = Mock()
    project = _project()
    profile = _profile()
    first_round = InterviewRound(id="round-1", series_id="series-1", round_number=1)
    second_round = InterviewRound(id="round-2", series_id="series-1", round_number=2)

    first = generator._get_or_create_round_document(db, project, profile, first_round)
    second = generator._get_or_create_round_document(db, project, profile, second_round)

    assert first.id != second.id
    assert first.interview_round_id == first_round.id
    assert second.interview_round_id == second_round.id
    assert first.guide_version == 1
    assert second.guide_version == 2
    assert first_round.guide_document_id == first.id
    assert second_round.guide_document_id == second.id


def test_source_context_deduplicates_unresolved_questions_and_topics():
    db = Mock()
    memo_a = InterviewInsightMemo(
        id="memo-a",
        session_id="session-a",
        topics_covered=["取消掛號", "跨科掛號"],
        unresolved_questions=[{"question": "臨時取消由誰核准？"}],
    )
    memo_b = InterviewInsightMemo(
        id="memo-b",
        session_id="session-b",
        topics_covered=["取消掛號"],
        unresolved_questions=[
            {"question": "臨時取消由誰核准？"},
            {"question": "資料如何同步？"},
        ],
    )
    db.query.return_value.filter.return_value.all.return_value = [memo_a, memo_b]

    context = InterviewRoundService._source_context(db, ["session-a", "session-b"])

    assert context["covered_topics"] == ["取消掛號", "跨科掛號"]
    assert context["unresolved_questions"] == ["臨時取消由誰核准？", "資料如何同步？"]


@pytest.mark.parametrize(
    ("mode", "expected_style"),
    [
        ("continue_unfinished", "structured"),
        ("follow_up", "exploratory"),
        ("validate", "validation"),
        ("new_scope", "exploratory"),
    ],
)
def test_generation_mode_selects_the_matching_guide_style(mode, expected_style):
    service = InterviewRoundService()
    interview_round = InterviewRound(
        id="round-1",
        series_id="series-1",
        round_number=1,
        generation_mode=mode,
        source_session_ids=[],
        focus_topics=[],
        exclude_completed_questions=True,
    )
    series = Mock(id="series-1", project_id="project-1", stakeholder_profile_id="profile-1")
    project = _project()
    profile = _profile()

    with (
        patch.object(service, "get_round", return_value=interview_round),
        patch(
            "app.services.interview_round_service.interview_series_service.get_series",
            return_value=series,
        ),
        patch(
            "app.services.interview_round_service.interview_series_service.get_project_and_profile",
            return_value=(project, profile),
        ),
        patch(
            "app.services.interview_round_service.stakeholder_card_generator.generate_cards_for_stakeholder",
            return_value={"document_id": "doc-1", "card_count": 1},
        ) as generate,
    ):
        service.generate_round_guide(Mock(), interview_round.id)

    assert generate.call_args.kwargs["options"]["interview_style"] == expected_style


def test_topic_key_is_stable_for_chinese_titles():
    assert InterviewSeriesService.normalize_topic_key("  掛號 作業／流程  ") == "掛號-作業流程"


def test_frozen_document_rejects_question_card_mutation():
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = Document(
        id="doc-history",
        user_id="user-1",
        title="歷史大綱",
        source_file_url="generated",
        file_type="generated",
        status="analyzed",
        is_frozen=True,
        created_at=datetime.utcnow(),
    )

    with pytest.raises(HTTPException) as exc_info:
        _ensure_document_editable(db, "doc-history")

    assert exc_info.value.status_code == 409
    assert "new interview round" in str(exc_info.value.detail).lower()
