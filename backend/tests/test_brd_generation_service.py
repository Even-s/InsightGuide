"""Tests for BRD generation output formatting."""

from datetime import datetime

from app.models.interview_theme import InterviewTheme
from app.models.utterance import Utterance
from app.services.brd_generation_service import brd_generation_service


def test_transcript_export_uses_plain_speaker_labels_without_emoji():
    """Exported transcript markdown should not include decorative speaker emoji."""
    utterances = [
        Utterance(
            id="utt-1",
            session_id="session-1",
            section_id="theme-1",
            speaker="interviewer",
            transcript="請說明主要目標。",
            created_at=datetime(2026, 6, 10, 10, 0, 0),
        ),
        Utterance(
            id="utt-2",
            session_id="session-1",
            section_id="theme-1",
            speaker="interviewee",
            transcript="主要目標是改善訪談效率。",
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

    assert "**Speaker (interviewer)**" in markdown
    assert "**Speaker (interviewee)**" in markdown
    assert "🎤" not in markdown
    assert "💬" not in markdown
