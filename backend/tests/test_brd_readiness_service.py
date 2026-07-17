"""Tests for BRD readiness source-of-truth contracts."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.brd_readiness_service import brd_readiness_service


def _query(*, first=None, rows=None):
    query = Mock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.first.return_value = first
    query.all.return_value = rows or []
    return query


def test_generate_report_reads_round_aggregate_entries_not_matrix_rows():
    """Readiness should evaluate entries derived directly from RoundAggregate."""
    entry = {
        "category": "business_process",
        "requirement_candidate": "櫃台需要快速確認掛號來源與號源狀態",
        "validation_status": "validated",
        "source_roles": ["frontline", "operations"],
        "supporting_evidence": [],
        "conflicts": [],
        "missing_validation_from": [],
        "mention_count": 2,
    }
    memo = SimpleNamespace(
        id="memo-1",
        pain_points=[{"description": "尖峰時段查詢分散"}],
        process_descriptions=[{"description": "先查病患身份再查號源"}],
        constraints_and_assumptions=[],
        stakeholder_summary={"role": "frontline"},
    )
    project = SimpleNamespace(id="project-1")
    slot = SimpleNamespace(
        priority="required",
        status="completed",
        role_label="櫃台人員",
        role_category="frontline",
    )
    profile = SimpleNamespace(stakeholder_type="frontline", status="interviewed")
    db = Mock()
    db.query.side_effect = [
        _query(first=project),
        _query(rows=[slot]),
        _query(rows=[profile]),
    ]

    with patch(
        "app.services.evidence_matrix_service.evidence_matrix_service.build_entries_from_round_aggregates",
        return_value=([entry], [memo]),
    ) as build_entries:
        report = brd_readiness_service.generate_report(db, "project-1")

    build_entries.assert_called_once_with(db, "project-1")
    assert report.total_evidence_entries == 1
    assert report.validated_requirements == 1
    assert report.ready_chapters
    assert db.query.call_count == 3
