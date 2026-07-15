"""API routes package."""

# InsightGuide routes
from app.api.routes import (
    auth,
    documents,
    events,
    interview_rounds,
    interview_sessions,
    prep_sessions,
    question_cards,
    realtime,
    sections,
    session_reports,
)

__all__ = [
    "documents",
    "sections",
    "question_cards",
    "interview_sessions",
    "interview_rounds",
    "auth",
    "realtime",
    "prep_sessions",
    "events",
    "session_reports",
]
