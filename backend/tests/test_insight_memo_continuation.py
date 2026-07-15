"""Regression coverage for cumulative insight analysis across continued visits."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.models.interview_session import InterviewSession
from app.models.live_utterance import LiveUtterance
from app.services.insight_memo_service import InsightMemoService


def _session(session_id: str, created_at: datetime) -> InterviewSession:
    return InterviewSession(
        id=session_id,
        prep_session_id="prep-1",
        document_id="doc-1",
        user_id="user-1",
        interview_round_id="round-1",
        status="ended",
        created_at=created_at,
    )


def test_analysis_sessions_include_every_earlier_visit_in_the_round():
    service = InsightMemoService()
    first = _session("session-1", datetime.utcnow() - timedelta(days=1))
    second = _session("session-2", datetime.utcnow())
    db = Mock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        first,
        second,
    ]

    sessions = service._analysis_sessions(db, second)

    assert [session.id for session in sessions] == ["session-1", "session-2"]


def test_transcript_analysis_keeps_visits_separate_and_includes_both():
    service = InsightMemoService()
    first_query = Mock()
    first_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        LiveUtterance(
            id="utt-1",
            session_id="session-1",
            speaker="realtime",
            transcript="第一次訪談內容",
            sequence_index=0,
            is_partial=False,
        )
    ]
    second_query = Mock()
    second_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        LiveUtterance(
            id="utt-2",
            session_id="session-2",
            speaker="realtime",
            transcript="第二次補充內容",
            sequence_index=0,
            is_partial=False,
        )
    ]
    db = Mock()
    db.query.side_effect = [first_query, second_query]

    transcript = service._load_transcript_text(db, ["session-1", "session-2"])

    assert "## 第 1 次訪談" in transcript
    assert "第一次訪談內容" in transcript
    assert "## 第 2 次訪談" in transcript
    assert "第二次補充內容" in transcript


def test_ai_prompt_explicitly_requests_cumulative_round_evaluation():
    service = InsightMemoService()
    session = _session("session-2", datetime.utcnow())

    with patch(
        "app.services.openai_service.openai_service.chat_completion",
        return_value={"topics_covered": []},
    ) as completion:
        service._ai_analyze_interview(
            stakeholder=None,
            qa_records=[],
            transcript_text="訪談內容",
            session=session,
            visit_count=2,
        )

    user_prompt = completion.call_args.kwargs["messages"][1]["content"]
    assert "合併同一輪的 2 次訪談" in user_prompt
    assert "不可只評估最後一場" in user_prompt
