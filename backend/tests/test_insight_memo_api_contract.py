"""Insight memo API contract regression tests."""

from unittest.mock import Mock, patch

from app.api.routes.insight_memos import _memo_to_response
from app.models.interview_insight_memo import InterviewInsightMemo
from app.services.insight_memo_service import InsightMemoService


def test_insight_memo_response_uses_question_summaries_without_legacy_key():
    memo = InterviewInsightMemo(
        id="memo-1",
        session_id="session-1",
        project_id="project-1",
        question_summaries=[
            {
                "question": "掛號需求怎麼進來？",
                "summary": "櫃台會先確認來源與病患資料。",
                "status": "covered",
                "confidence": 0.9,
            }
        ],
        topics_covered=[],
        pain_points=[],
        requirement_candidates=[],
        constraints_and_assumptions=[],
        process_descriptions=[],
        unresolved_questions=[],
        next_interview_suggestions=[],
        status="completed",
    )

    response = _memo_to_response(memo)

    assert response["questionSummaries"] == memo.question_summaries
    assert "qa" + "Summaries" not in response


def test_project_memo_list_reads_current_memos_from_round_aggregates():
    service = InsightMemoService()
    db = Mock()
    memo = InterviewInsightMemo(id="memo-current", session_id="session-current")

    with patch(
        "app.services.interview_round_aggregate_service.interview_round_aggregate_service.latest_memos_for_project",
        return_value=[memo],
    ) as latest_memos:
        result = service.get_current_memos_for_project(db, "project-1")

    assert result == [memo]
    latest_memos.assert_called_once_with(db, "project-1")
    db.query.assert_not_called()
