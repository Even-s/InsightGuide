"""Evidence Matrix clean-break source-of-truth contracts."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.api.routes.evidence_matrix import get_evidence_matrix, refresh_evidence_matrix
from app.api.routes import evidence_matrix
from app.models import requirement_evidence_matrix
from app.services.evidence_matrix_service import evidence_matrix_service


@pytest.mark.asyncio
async def test_get_evidence_matrix_reads_round_aggregate_entries_not_snapshot_rows():
    """GET matrix should derive entries from RoundAggregate instead of persisted snapshots."""
    entry = {
        "requirement_candidate": "櫃台需要快速確認掛號來源",
        "category": "business_process",
        "source_roles": ["frontline"],
        "source_memo_ids": ["memo-1"],
        "supporting_evidence": [{"memo_id": "memo-1", "evidence_quote": "先看來源"}],
        "conflicts": [],
        "validation_status": "candidate",
        "missing_validation_from": ["operations"],
        "mention_count": 1,
        "stakeholder_agreement_level": "single_source",
    }
    memo = SimpleNamespace(id="memo-1", generated_at=datetime(2026, 7, 17, 9, 0, 0))
    db = Mock()

    with patch(
        "app.api.routes.evidence_matrix.evidence_matrix_service.build_entries_from_round_aggregates",
        return_value=([entry], [memo]),
    ) as build_entries:
        result = await get_evidence_matrix("project-1", db)

    build_entries.assert_called_once_with(db, "project-1")
    db.query.assert_not_called()
    assert result["matrix"]["status"] == "derived"
    assert result["matrix"]["source"] == "round_aggregate"
    assert result["entries"][0]["editable"] is False
    assert result["entries"][0]["requirementCandidate"] == "櫃台需要快速確認掛號來源"


def test_matrix_summary_reads_round_aggregate_entries_not_snapshot_rows():
    entry = {
        "validation_status": "needs_more_evidence",
        "source_roles": ["frontline"],
        "missing_validation_from": ["operations"],
    }
    memo = SimpleNamespace(id="memo-1", generated_at=datetime(2026, 7, 17, 9, 0, 0))
    db = Mock()

    with patch.object(
        evidence_matrix_service,
        "build_entries_from_round_aggregates",
        return_value=([entry], [memo]),
    ) as build_entries:
        summary = evidence_matrix_service.get_matrix_summary(db, "project-1")

    build_entries.assert_called_once_with(db, "project-1")
    db.query.assert_not_called()
    assert summary["status"] == "derived"
    assert summary["total_candidates"] == 1
    assert summary["needs_more_evidence"] == 1
    assert summary["roles_missing"] == ["operations"]


def test_evidence_matrix_router_does_not_expose_entry_update_endpoint():
    paths = {
        (method, route.path)
        for route in evidence_matrix.router.routes
        for method in getattr(route, "methods", set())
    }

    assert ("PUT", "/evidence-matrix-entries/{entry_id}") not in paths


def test_clean_baseline_does_not_define_persisted_matrix_entry_rows():
    """Evidence Matrix rows are derived from RoundAggregate and not snapshot tables."""
    assert not hasattr(requirement_evidence_matrix, "EvidenceMatrixEntry")

    baseline_path = (
        Path(__file__).resolve().parents[1]
        / "app/db/migrations/versions/0001_clean_v2_baseline_clean_v2_baseline.py"
    )
    baseline_source = baseline_path.read_text(encoding="utf-8")
    assert 'op.create_table(\n        "evidence_matrix_entries"' not in baseline_source


@pytest.mark.asyncio
async def test_refresh_evidence_matrix_response_uses_round_aggregate_entries_not_snapshot_rows():
    entry = {
        "requirement_candidate": "需要顯示號源狀態",
        "source_roles": ["frontline"],
        "source_memo_ids": ["memo-1"],
        "supporting_evidence": [],
        "conflicts": [],
        "validation_status": "validated",
        "missing_validation_from": [],
        "mention_count": 2,
        "stakeholder_agreement_level": "majority",
    }
    memo = SimpleNamespace(id="memo-1", generated_at=datetime(2026, 7, 17, 9, 0, 0))
    matrix = SimpleNamespace(
        id="matrix-1",
        project_id="project-1",
        status="ready",
        memo_count=1,
        last_updated_at=datetime(2026, 7, 17, 9, 1, 0),
        _derived_entries=[entry],
        _source_memos=[memo],
    )
    db = Mock()

    with patch(
        "app.api.routes.evidence_matrix.evidence_matrix_service.update_matrix",
        return_value=matrix,
    ) as update_matrix:
        result = await refresh_evidence_matrix("project-1", db)

    update_matrix.assert_called_once_with(db, "project-1")
    db.query.assert_not_called()
    assert result["matrix"]["source"] == "round_aggregate"
    assert result["entries"][0]["validationStatus"] == "validated"
