"""API routes package."""

# InsightGuide routes
from app.api.routes import documents
from app.api.routes import sections
from app.api.routes import question_cards
from app.api.routes import interview_sessions
from app.api.routes import auth
from app.api.routes import realtime
from app.api.routes import prep_sessions
from app.api.routes import events
from app.api.routes import session_reports

__all__ = [
    "documents",
    "sections",
    "question_cards",
    "interview_sessions",
    "auth",
    "realtime",
    "prep_sessions",
    "events",
    "session_reports",
]
