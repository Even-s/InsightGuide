"""Regression tests for canonical per-round aggregate outputs."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.models.interview_insight_memo import InterviewInsightMemo
from app.models.interview_round_aggregate import InterviewRoundAggregate
from app.models.requirement_evidence_matrix import RequirementEvidenceMatrix
from app.services.evidence_matrix_service import evidence_matrix_service
from app.services.interview_round_aggregate_service import (
    InterviewRoundAggregateService,
    interview_round_aggregate_service,
)


def _query(*, first=None, rows=None):
    query = Mock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.first.return_value = first
    query.all.return_value = rows or []
    return query


def test_rebuild_points_to_latest_memo_and_snapshots_latest_round_state():
    service = InterviewRoundAggregateService()
    aggregate = InterviewRoundAggregate(
        id="roundagg-1",
        round_id="round-1",
        version=2,
        status="stale",
    )
    sessions = [
        SimpleNamespace(id="session-1"),
        SimpleNamespace(id="session-2"),
    ]
    memo = SimpleNamespace(id="memo-latest")
    card_state = SimpleNamespace(
        question_card_id="card-1",
        status="sufficient",
        confidence=0.9,
        evidence_transcript="已說明流程",
        evidence={"quote": "已說明流程"},
        answered_at=datetime(2026, 7, 15, 10, 0, 0),
    )
    criterion = SimpleNamespace(
        card_id="card-1",
        criterion_id="criterion-1",
        status="satisfied",
        evidence_quote="已說明流程",
        normalized_value="流程 A",
        evaluator_confidence=0.95,
        session_id="session-2",
    )

    db = Mock()
    db.query.side_effect = [
        _query(first=SimpleNamespace(id="round-1")),
        _query(rows=sessions),
        _query(first=memo),
        _query(rows=[card_state]),
        _query(rows=[criterion]),
    ]

    with (
        patch.object(service, "get", return_value=aggregate),
        patch.object(service, "_invalidate_project_outputs") as invalidate,
    ):
        result = service.rebuild(db, "round-1")

    assert result.latest_memo_id == "memo-latest"
    assert result.source_session_ids == ["session-1", "session-2"]
    assert result.coverage_snapshot["sourceSessionId"] == "session-2"
    assert result.coverage_snapshot["counts"] == {"sufficient": 1}
    assert result.evidence_snapshot[0]["sourceSessionId"] == "session-2"
    assert result.status == "ready"
    assert result.version == 3
    invalidate.assert_called_once_with(db, "round-1")


def test_evidence_matrix_uses_one_aggregate_memo_instead_of_all_session_memos():
    matrix = RequirementEvidenceMatrix(
        id="matrix-1",
        project_id="project-1",
        status="stale",
        memo_count=0,
    )
    memo = InterviewInsightMemo(
        id="memo-latest",
        session_id="session-2",
        project_id="project-1",
        requirement_candidates=[],
        status="completed",
        interview_date=datetime(2026, 7, 15),
    )
    db = Mock()

    with (
        patch.object(evidence_matrix_service, "get_or_create_matrix", return_value=matrix),
        patch.object(
            interview_round_aggregate_service,
            "latest_memos_for_project",
            return_value=[memo],
        ) as latest_memos,
        patch(
            "app.services.stakeholder_plan_service.stakeholder_plan_service._update_slot_statuses"
        ),
    ):
        result = evidence_matrix_service.update_matrix(db, "project-1")

    latest_memos.assert_called_once_with(db, "project-1")
    assert result.status == "ready"
    assert result.memo_count == 1
    assert result.last_memo_id == "memo-latest"
