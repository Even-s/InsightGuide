"""Background service to clean up stale presentation sessions."""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.interview_session import InterviewSession

logger = logging.getLogger(__name__)


class SessionCleanupService:
    """Service to automatically clean up old/stale sessions."""

    def cleanup_stale_sessions(
        self,
        db: Session,
        max_duration_hours: int = 24
    ) -> int:
        """
        End sessions that have been running for too long.

        Args:
            db: Database session
            max_duration_hours: Maximum hours a session can run (default: 24)

        Returns:
            Number of sessions ended
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_duration_hours)

        stale_sessions = db.query(InterviewSession).filter(
            InterviewSession.status.in_(['presenting', 'paused', 'ready']),
            InterviewSession.started_at < cutoff_time
        ).all()

        count = 0
        for session in stale_sessions:
            old_status = session.status
            session.status = 'ended'
            session.ended_at = datetime.utcnow()
            count += 1

            logger.info(
                f"Auto-ended stale session {session.id} "
                f"(was {old_status} for {max_duration_hours}+ hours)"
            )

        if count > 0:
            db.commit()
            logger.info(f"Cleaned up {count} stale sessions")

        return count

    def cleanup_old_sessions(
        self,
        db: Session,
        days_to_keep: int = 30
    ) -> int:
        """
        Delete old completed sessions.

        Args:
            db: Database session
            days_to_keep: Number of days to keep sessions (default: 30)

        Returns:
            Number of sessions deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        deleted = db.query(InterviewSession).filter(
            InterviewSession.status == 'ended',
            InterviewSession.ended_at < cutoff_date
        ).delete()

        if deleted > 0:
            db.commit()
            logger.info(f"Deleted {deleted} old sessions (older than {days_to_keep} days)")

        return deleted


# Singleton instance
session_cleanup_service = SessionCleanupService()
