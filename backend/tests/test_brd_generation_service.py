"""Tests for project-level BRD generation formatting."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.brd_generation_service import brd_generation_service


def _query(*, first=None, rows=None):
    query = Mock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.first.return_value = first
    query.all.return_value = rows or []
    return query


def test_project_brd_chapters_use_project_evidence_and_memos():
    """BRD content should be built from RoundAggregate-derived entries."""
    entry = {
        "category": "business_process",
        "requirement_candidate": "櫃台需要快速確認掛號來源與號源狀態",
        "validation_status": "validated",
        "supporting_evidence": [
            {
                "stakeholder_name": "王小明",
                "evidence_quote": "櫃台會先看病患身份、預約來源和號源是否還有空位。",
            }
        ],
        "source_roles": ["frontline"],
        "mention_count": 2,
    }
    memo = SimpleNamespace(
        pain_points=[
            {
                "description": "尖峰時段資訊分散，櫃台容易重複查詢。",
                "evidence_quote": "人多時要在不同系統切換，很容易漏看。",
                "affected_roles": ["frontline"],
            }
        ],
        constraints_and_assumptions=[],
    )

    chapters = brd_generation_service._build_project_brd_chapters(
        [entry],
        [memo],
        project=SimpleNamespace(title="掛號系統"),
    )

    assert [chapter["chapter"] for chapter in chapters] == ["業務流程需求", "業務痛點"]
    assert chapters[0]["confirmedItems"][0]["focusText"] == "櫃台需要快速確認掛號來源與號源狀態"
    assert "櫃台會先看病患身份" in chapters[0]["confirmedItems"][0]["evidence"]
    assert chapters[1]["confirmedItems"][0]["focusText"] == "尖峰時段資訊分散，櫃台容易重複查詢。"


def test_session_brd_output_helpers_are_removed():
    """Clean-break BRD service should not expose session report/transcript helpers."""
    assert not hasattr(brd_generation_service, "generate_outputs")
    assert not hasattr(brd_generation_service, "_build_transcript")
    assert not hasattr(brd_generation_service, "_build_brd_sections")
    assert not hasattr(brd_generation_service, "_build_project_brd_sections")


def test_generate_project_brd_reads_round_aggregate_entries_not_matrix_rows():
    """Project BRD generation should not query persisted EvidenceMatrixEntry rows."""
    entry = {
        "category": "business_process",
        "requirement_candidate": "櫃台需要快速確認掛號來源與號源狀態",
        "validation_status": "validated",
        "supporting_evidence": [
            {
                "stakeholder_name": "王小明",
                "evidence_quote": "櫃台會先看病患身份、預約來源和號源是否還有空位。",
            }
        ],
        "source_roles": ["frontline"],
        "mention_count": 2,
    }
    memo = SimpleNamespace(
        pain_points=[],
        constraints_and_assumptions=[],
    )
    project = SimpleNamespace(id="project-1", title="掛號系統", brd_scope={})
    profile = SimpleNamespace(
        name="王小明",
        role_title="櫃台組長",
        stakeholder_type="frontline",
        department="門診",
        decision_power="user",
    )
    db = Mock()
    db.query.side_effect = [
        _query(first=project),
        _query(rows=[profile]),
    ]

    with (
        patch(
            "app.services.evidence_matrix_service.evidence_matrix_service.build_entries_from_round_aggregates",
            return_value=([entry], [memo]),
        ) as build_entries,
        patch.object(
            brd_generation_service,
            "_rewrite_chapters_with_ai",
            side_effect=lambda _document, chapters, **_kwargs: chapters,
        ),
    ):
        result = brd_generation_service.generate_project_brd(db, "project-1")

    build_entries.assert_called_once_with(db, "project-1")
    assert result["brd"]["chapters"][0]["chapter"] == "業務流程需求"
    assert result["evidence"]["validatedEntries"] == 1
    assert db.query.call_count == 2
