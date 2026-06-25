"""API dependencies - common dependency injection helpers."""

from app.api.routes.auth import get_current_user
from app.db.session import get_db

__all__ = ["get_db", "get_current_user"]
