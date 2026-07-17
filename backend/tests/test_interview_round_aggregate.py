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


def _query(*, first=None, rows=None, scalar=None):
    query = Mock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.join.return_value = query
    query.first.return_value = first
    query.all.return_value = rows or []
    query.scalar.return_value = scalar
    query.delete.return_value = 0
    return query


def test_rebuild_points_to_latest_memo_and_snapshots_cumulative_round_state():
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
    first_session_state = SimpleNamespace(
        id="state-1",
        session_id="session-1",
        question_card_id="card-1",
        status="sufficient",
        confidence=0.8,
        evidence_transcript="第一次已說明來源",
        evidence={"quote": "第一次已說明來源"},
        answered_at=datetime(2026, 7, 15, 9, 0, 0),
    )
    latest_same_card_state = SimpleNamespace(
        id="state-2",
        session_id="session-2",
        question_card_id="card-1",
        status="manually_checked",
        confidence=0.9,
        evidence_transcript="第二次補充確認",
        evidence={"quote": "第二次補充確認"},
        answered_at=datetime(2026, 7, 15, 10, 0, 0),
    )
    second_card_state = SimpleNamespace(
        id="state-3",
        session_id="session-1",
        question_card_id="card-2",
        status="sufficient",
        confidence=0.7,
        evidence_transcript="第一次已說明限制",
        evidence={"quote": "第一次已說明限制"},
        answered_at=datetime(2026, 7, 15, 9, 5, 0),
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
        _query(rows=[first_session_state, latest_same_card_state, second_card_state]),
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
    assert result.coverage_snapshot["sourceSessionIds"] == ["session-1", "session-2"]
    assert result.coverage_snapshot["mergeMode"] == "latest_state_per_question_card"
    assert result.coverage_snapshot["counts"] == {"manually_checked": 1, "sufficient": 1}
    assert result.coverage_snapshot["cards"] == [
        {
            "cardId": "card-1",
            "status": "manually_checked",
            "confidence": 0.9,
            "evidenceTranscript": "第二次補充確認",
            "evidence": {"quote": "第二次補充確認"},
            "answeredAt": "2026-07-15T10:00:00",
            "sourceSessionId": "session-2",
        },
        {
            "cardId": "card-2",
            "status": "sufficient",
            "confidence": 0.7,
            "evidenceTranscript": "第一次已說明限制",
            "evidence": {"quote": "第一次已說明限制"},
            "answeredAt": "2026-07-15T09:05:00",
            "sourceSessionId": "session-1",
        },
    ]
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


def test_latest_memos_for_project_reads_from_ready_aggregates():
    service = InterviewRoundAggregateService()
    memo = InterviewInsightMemo(
        id="memo-latest",
        session_id="session-2",
        project_id="project-1",
        requirement_candidates=[],
        status="completed",
        interview_date=datetime(2026, 7, 15),
    )
    aggregate = SimpleNamespace(latest_memo=memo)
    db = Mock()

    with patch.object(
        service,
        "ready_aggregates_for_project",
        return_value=[aggregate, SimpleNamespace(latest_memo=None)],
    ) as ready_aggregates:
        result = service.latest_memos_for_project(db, "project-1")

    ready_aggregates.assert_called_once_with(db, "project-1")
    assert result == [memo]


def test_invalidate_project_outputs_marks_derivatives_stale():
    service = InterviewRoundAggregateService()
    matrix = RequirementEvidenceMatrix(
        id="matrix-1",
        project_id="project-1",
        status="ready",
    )
    project_query = _query(scalar="project-1")
    matrix_query = _query(first=matrix)
    readiness_query = _query()
    db = Mock()
    db.query.side_effect = [
        project_query,
        matrix_query,
        readiness_query,
    ]

    service._invalidate_project_outputs(db, "round-1")

    assert matrix.status == "stale"
    readiness_query.filter.assert_called_once()
    readiness_query.delete.assert_called_once_with(synchronize_session=False)
