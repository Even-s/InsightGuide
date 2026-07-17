"""Prep session management service."""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.interview_session import InterviewSession
from app.models.prep_session import PrepSession
from app.schemas.prep_session import (
    PrepSessionCreate,
    PrepSessionListResponse,
    PrepSessionUpdate,
    PrepSessionWithDocument,
)
from app.services.billing_service import billing_service

logger = logging.getLogger(__name__)


class PrepSessionService:
    """Service for prep session operations."""

    def create_prep_session(
        self, db: Session, user_id: str, prep_session_data: PrepSessionCreate
    ) -> PrepSession:
        """
        Create a new prep session.

        Args:
            db: Database session
            user_id: User ID
            prep_session_data: Prep session creation data

        Returns:
            Created prep session
        """
        # Verify document exists
        document = db.query(Document).filter(Document.id == prep_session_data.documentId).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {prep_session_data.documentId} not found",
            )

        # Verify document belongs to user
        if document.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to create a prep session for this document",
            )

        # Check if a prep session already exists for this document
        existing = (
            db.query(PrepSession).filter(PrepSession.id == prep_session_data.documentId).first()
        )

        if existing:
            logger.info(f"Prep session already exists for document {prep_session_data.documentId}")
            return existing

        # Create prep session with appropriate status based on document status
        # - If document is already analyzed: set to "ready"
        # - Otherwise: set to "preparing" (will be updated when analysis completes)
        prep_session_status = "ready" if document.status == "analyzed" else "preparing"

        prep_session = PrepSession(
            id=prep_session_data.documentId,
            document_id=prep_session_data.documentId,
            user_id=user_id,
            title=prep_session_data.title,
            status=prep_session_status,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(prep_session)
        db.commit()
        db.refresh(prep_session)

        logger.info(
            f"Created prep session {prep_session.id} for document {prep_session_data.documentId}"
        )

        return prep_session

    def get_prep_session(self, db: Session, prep_session_id: str) -> PrepSession:
        """Get prep session by ID."""
        prep_session = db.query(PrepSession).filter(PrepSession.id == prep_session_id).first()

        if not prep_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prep session {prep_session_id} not found",
            )

        return prep_session

    def update_prep_session(
        self, db: Session, prep_session_id: str, update_data: PrepSessionUpdate
    ) -> PrepSession:
        """Update prep session."""
        prep_session = self.get_prep_session(db, prep_session_id)

        if update_data.title is not None:
            prep_session.title = update_data.title

        if update_data.status is not None:
            prep_session.status = update_data.status

        prep_session.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(prep_session)

        logger.info(f"Updated prep session {prep_session_id}")

        return prep_session

    def delete_prep_session(self, db: Session, prep_session_id: str) -> None:
        """
        Delete a prep session and all related data including the document.

        This will delete:
        - Prep session
        - All interview sessions (cascade)
        - The associated document
        - All interview themes (cascade from document)
        - All question cards (cascade from document)

        Args:
            db: Database session
            prep_session_id: Prep session ID to delete

        Raises:
            HTTPException: If prep session not found
        """
        prep_session = self.get_prep_session(db, prep_session_id)
        document_id = prep_session.document_id

        try:
            from app.services.document_service import document_service

            # The document is the aggregate root for uploaded content. Deleting it
            # cascades to prep sessions, interview sessions, interview themes, question
            # cards, card states, and utterances in one database transaction.
            document_service.delete_document(db, document_id, commit=False)
            db.commit()
            logger.info(
                f"Deleted prep session {prep_session_id} and associated document {document_id}"
            )
        except Exception as e:
            db.rollback()
            logger.error(
                f"Failed to delete prep session {prep_session_id} and document {document_id}: {e}",
                exc_info=True,
            )
            raise

    def delete_all_prep_sessions(self, db: Session, user_id: str) -> None:
        """
        Delete ALL prep sessions for a user and all related data.

        WARNING: This is a destructive operation.

        Args:
            db: Database session
            user_id: User ID whose prep sessions to delete
        """
        prep_sessions = db.query(PrepSession).filter(PrepSession.user_id == user_id).all()
        document_ids = [prep_session.document_id for prep_session in prep_sessions]

        try:
            from app.services.document_service import document_service

            for document_id in document_ids:
                document_service.delete_document(db, document_id, commit=False)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                f"Failed to delete all prep sessions for user {user_id}: {e}",
                exc_info=True,
            )
            raise

        logger.warning(
            f"Deleted ALL {len(prep_sessions)} prep sessions and {len(document_ids)} documents for user {user_id}"
        )

    def list_prep_sessions(
        self,
        db: Session,
        user_id: str,
        status_filter: Optional[str] = None,
        document_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "createdAt",
        order: str = "desc",
    ) -> PrepSessionListResponse:
        """
        List prep sessions with filtering, sorting, and pagination.

        Args:
            db: Database session
            user_id: User ID (for filtering)
            status_filter: Filter by prep session status
            document_id: Filter by document ID
            limit: Maximum number of prep sessions to return
            offset: Number of prep sessions to skip
            sort_by: Field to sort by (createdAt, updatedAt, status)
            order: Sort order (asc or desc)

        Returns:
            PrepSessionListResponse with prep sessions and pagination info
        """
        query = db.query(PrepSession).join(Document).filter(PrepSession.user_id == user_id)

        # Apply filters
        if status_filter:
            query = query.filter(PrepSession.status == status_filter)
        if document_id:
            query = query.filter(PrepSession.document_id == document_id)

        # Get total count before pagination
        total = query.count()

        # Apply sorting
        sort_field = getattr(PrepSession, self._get_sort_field(sort_by))
        if order == "desc":
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(asc(sort_field))

        # Apply pagination
        prep_sessions = query.offset(offset).limit(limit).all()
        document_usage = billing_service.summarize_documents(
            db,
            [prep_session.document_id for prep_session in prep_sessions],
        )

        # Convert to response schema with document info and interview session count
        prep_sessions_with_document = []
        for prep_session in prep_sessions:
            usage = document_usage.get(prep_session.document_id, billing_service.empty_summary())
            # Count interview sessions for this prep session
            interview_count = (
                db.query(func.count(InterviewSession.id))
                .filter(InterviewSession.prep_session_id == prep_session.id)
                .scalar()
            )

            prep_sessions_with_document.append(
                PrepSessionWithDocument(
                    id=prep_session.id,
                    documentId=prep_session.document_id,
                    documentTitle=prep_session.document.title,
                    userId=prep_session.user_id,
                    title=prep_session.title,
                    status=prep_session.status,
                    createdAt=prep_session.created_at,
                    updatedAt=prep_session.updated_at,
                    interviewSessionsCount=interview_count or 0,
                    documentCostUsd=usage["totalCostUsd"],
                    documentAiUsage=usage,
                )
            )

        return PrepSessionListResponse(
            prepSessions=prep_sessions_with_document, total=total, limit=limit, offset=offset
        )

    def _get_sort_field(self, sort_by: str) -> str:
        """Map sort_by string to model field name."""
        field_map = {"createdAt": "created_at", "updatedAt": "updated_at", "status": "status"}
        return field_map.get(sort_by, "created_at")

    def get_prep_session_interview_sessions(
        self, db: Session, prep_session_id: str
    ) -> List[InterviewSession]:
        """Get all interview sessions for a prep session."""
        self.get_prep_session(db, prep_session_id)  # Verify prep session exists

        sessions = (
            db.query(InterviewSession)
            .filter(InterviewSession.prep_session_id == prep_session_id)
            .order_by(InterviewSession.created_at.desc())
            .all()
        )

        return sessions


# Singleton instance
prep_session_service = PrepSessionService()
