"""Clean-break contracts for interview session and transcript schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.interview import (
    InterviewSessionCreate,
    InterviewSessionUpdate,
    UtteranceCreate,
)


@pytest.mark.parametrize(
    ("schema_cls", "payload"),
    [
        (
            UtteranceCreate,
            {
                "transcript": "這是逐字稿。",
                "themeId": "theme-1",
                "sectionId": "section-1",
            },
        ),
        (
            UtteranceCreate,
            {
                "transcript": "這是逐字稿。",
                "themeId": "theme-1",
                "speaker": "interviewee",
            },
        ),
        (
            UtteranceCreate,
            {
                "transcript": "這是逐字稿。",
                "themeId": "theme-1",
                "askedCardId": "card-1",
            },
        ),
        (
            InterviewSessionCreate,
            {
                "prepSessionId": "prep-1",
                "documentId": "doc-1",
                "currentSectionId": "section-1",
            },
        ),
        (
            InterviewSessionUpdate,
            {
                "currentThemeId": "theme-1",
                "currentSectionId": "section-1",
            },
        ),
    ],
)
def test_clean_break_schemas_reject_retired_contract_fields(schema_cls, payload):
    """Retired deck/section/speaker/single-card fields must fail instead of being ignored."""
    with pytest.raises(ValidationError):
        schema_cls(**payload)


def test_utterance_create_accepts_theme_and_multiple_asked_cards_only():
    utterance = UtteranceCreate(
        transcript="這是逐字稿。",
        themeId="theme-1",
        askedCardIds=["card-1", "card-2"],
        realtimeItemId="rt-1",
    )

    assert utterance.themeId == "theme-1"
    assert utterance.askedCardIds == ["card-1", "card-2"]
    assert not hasattr(utterance, "sectionId")
    assert not hasattr(utterance, "askedCardId")
