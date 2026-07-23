"""API routes package."""

# InsightGuide routes
from app.api.routes import (
    auth,
    demo_sessions,
    documents,
    events,
    interview_rounds,
    interview_sessions,
    prep_sessions,
    question_cards,
    realtime,
)

__all__ = [
    "documents",
    "demo_sessions",
    "question_cards",
    "interview_sessions",
    "interview_rounds",
    "auth",
    "realtime",
    "prep_sessions",
    "events",
]
