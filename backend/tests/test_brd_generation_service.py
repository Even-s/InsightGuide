"""Tests for BRD generation output formatting."""

from datetime import datetime

from app.models.interview_theme import InterviewTheme
from app.models.live_utterance import LiveUtterance
from app.services.brd_generation_service import brd_generation_service


def test_transcript_export_is_speaker_neutral():
    """Exported Realtime transcript should not assign speaker roles."""
    utterances = [
        LiveUtterance(
            id="utt-1",
            session_id="session-1",
            speaker="realtime",
            transcript="請說明主要目標。",
            sequence_index=0,
            is_partial=False,
            created_at=datetime(2026, 6, 10, 10, 0, 0),
        ),
        LiveUtterance(
            id="utt-2",
            session_id="session-1",
            speaker="realtime",
            transcript="主要目標是改善訪談效率。",
            sequence_index=1,
            is_partial=False,
            created_at=datetime(2026, 6, 10, 10, 1, 0),
        ),
    ]
    themes = [
        InterviewTheme(
            id="theme-1",
            document_id="doc-1",
            theme_number=1,
            title="目標確認",
        )
    ]

    markdown = brd_generation_service._build_transcript(utterances, themes)

    assert "請說明主要目標。" in markdown
    assert "主要目標是改善訪談效率。" in markdown
    assert "interviewer" not in markdown
    assert "interviewee" not in markdown
    assert "🎤" not in markdown
    assert "💬" not in markdown
