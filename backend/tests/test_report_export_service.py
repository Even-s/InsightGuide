"""Tests for session report export generation."""

import json
from types import SimpleNamespace

from app.services.report_export_service import report_export_service


def sample_report():
    return {
        "session_id": "session_test",
        "generated_at": "2026-06-02T00:00:00Z",
        "coverage_stats": {
            "coverage_percentage": 82.5,
            "must_coverage_percentage": 100,
            "should_coverage_percentage": 75,
            "total_cards": 4,
            "covered": 2,
            "probably_covered": 1,
            "skipped": 0,
            "at_risk": 1,
            "pending": 0,
        },
        "performance_metrics": {
            "total_duration_seconds": 245,
            "total_utterances": 12,
            "total_characters": 980,
            "characters_per_minute": 240.0,
        },
        "insights": {
            "strengths": [{"description": "Covered all required topics."}],
            "areas_for_improvement": [{"description": "Spend more time on closing."}],
            "recommendations": [{"recommendation": "Practice the final slide once more."}],
        },
        "topic_analysis": [
            {
                "slide_page": 1,
                "title": "市場痛點 & Product fit",
                "importance": "must",
                "status": "covered",
                "confidence": 0.91,
            }
        ],
    }


def test_build_json_export_contains_report_payload():
    report = sample_report()

    content = report_export_service._build_json_export(report)

    decoded = json.loads(content.decode("utf-8"))
    assert decoded["session_id"] == "session_test"
    assert decoded["topic_analysis"][0]["title"] == "市場痛點 & Product fit"


def test_build_pdf_export_returns_pdf_bytes():
    report = sample_report()
    session = SimpleNamespace(deck=SimpleNamespace(title="Demo & 測試 Deck"))

    content = report_export_service._build_pdf_export(report, session)

    assert content.startswith(b"%PDF")
    assert len(content) > 1000
