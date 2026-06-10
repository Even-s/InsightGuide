"""Document service for business logic."""

import logging
import uuid
from datetime import datetime
from typing import Optional
from io import BytesIO

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.user import User
from app.services.s3_service import s3_service
from app.core.config import settings
from app.db.session import SessionLocal
# Avoid circular import - import analyze_document inside the function where it's used

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document operations."""

    @staticmethod
    def validate_file(file: UploadFile) -> None:
        """
        Validate uploaded file.

        Args:
            file: Uploaded file

        Raises:
            HTTPException: If file is invalid
        """
        # Check file extension
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided"
            )

        file_ext = file.filename.split(".")[-1].lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        # Note: File size validation should be done at middleware level
        # or we can check here if file.size is available

    @staticmethod
    def create_document(
        db: Session,
        file: UploadFile,
        title: Optional[str] = None,
        user_id: str = "user_default"  # TODO: Get from auth
    ) -> Document:
        """
        Create a new document from uploaded file.

        Args:
            db: Database session
            file: Uploaded requirements document file (PDF, Word, Markdown, Text)
            title: Optional document title (defaults to filename)
            user_id: User ID creating the document

        Returns:
            Created Document instance

        Raises:
            HTTPException: If file validation fails or upload fails
        """
        # Validate file
        DocumentService.validate_file(file)

        # Generate document ID
        document_id = f"doc_{uuid.uuid4().hex[:12]}"

        # Use filename as title if not provided
        if not title:
            title = file.filename.rsplit(".", 1)[0]

        # Get file extension
        file_ext = file.filename.split(".")[-1].lower()

        # Generate S3 object key
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        object_key = f"documents/{document_id}/source/{timestamp}.{file_ext}"

        try:
            # Read file content
            file_content = file.file.read()
            file_obj = BytesIO(file_content)

            # Determine content type
            content_type_map = {
                "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "doc": "application/msword",
                "md": "text/markdown",
                "txt": "text/plain"
            }
            content_type = file.content_type or content_type_map.get(file_ext, "application/octet-stream")

            # Upload to S3
            source_file_url = s3_service.upload_file(
                file_obj,
                object_key,
                content_type=content_type
            )

            logger.info(f"Uploaded file to {source_file_url}")

        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file"
            )

        # Create document record
        document = Document(
            id=document_id,
            user_id=user_id,
            title=title,
            source_file_url=source_file_url,
            file_type=file_ext,
            status="uploaded",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        try:
            db.add(document)
            db.commit()
            db.refresh(document)
            logger.info(f"Created document {document_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create document record: {e}")
            # Clean up uploaded file
            try:
                s3_service.delete_file(object_key)
            except:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create document"
            )

        # Auto-create PrepSession immediately for this document
        # This ensures the prep session exists before analysis completes
        try:
            from app.models.prep_session import PrepSession

            prep_session = PrepSession(
                id=document_id,  # Same as document_id for 1:1 mapping
                document_id=document_id,
                user_id=user_id,
                title=f"{title} - Prep Session",
                status="preparing",  # Will be updated to "ready" when analysis completes
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(prep_session)
            db.commit()
            logger.info(f"Created prep session {document_id} for document")

            # Publish global event for prep session creation
            try:
                from app.services.event_service import event_service
                event_service.publish_sync(f"prep_sessions_global", {
                    'type': 'PREP_SESSION_CREATED',
                    'prepSessionId': prep_session.id,
                    'documentId': prep_session.document_id,
                    'status': prep_session.status,
                    'title': prep_session.title
                })
                logger.info(f"📤 Published PREP_SESSION_CREATED event for {prep_session.id}")
            except Exception as e:
                logger.warning(f"Failed to publish prep session created event: {e}")

        except Exception as e:
            logger.warning(f"Failed to create prep session: {e}")
            # Don't fail the document creation if prep session creation fails

        # Enqueue document processing job
        try:
            from app.workers.document_analysis_worker import analyze_document
            try:
                analyze_document.delay(document_id)
                logger.info(f"Enqueued document processing job for document {document_id}")
            except Exception:
                # Celery not available — run synchronously in background thread
                import threading
                def _run_analysis():
                    try:
                        analyze_document(document_id)
                        # Update prep session to ready after analysis
                        from app.models.prep_session import PrepSession
                        analysis_db = SessionLocal()
                        ps = analysis_db.query(PrepSession).filter(PrepSession.id == document_id).first()
                        if ps:
                            ps.status = "ready"
                            analysis_db.commit()
                        analysis_db.close()
                    except Exception as thread_err:
                        logger.error(f"Background analysis failed: {thread_err}")

                thread = threading.Thread(target=_run_analysis, daemon=True)
                thread.start()
                logger.info(f"Started background analysis thread for document {document_id}")

        except Exception as e:
            logger.error(f"Failed to start document processing: {e}")

        return document

    @staticmethod
    def get_document(db: Session, document_id: str) -> Document:
        """
        Get document by ID.

        Args:
            db: Database session
            document_id: Document ID

        Returns:
            Document instance

        Raises:
            HTTPException: If document not found
        """
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        return document

    @staticmethod
    def update_document_status(
        db: Session,
        document_id: str,
        status: str
    ) -> Document:
        """
        Update document status.

        Args:
            db: Database session
            document_id: Document ID
            status: New status

        Returns:
            Updated Document instance
        """
        document = DocumentService.get_document(db, document_id)
        document.status = status
        document.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(document)
        logger.info(f"Updated document {document_id} status to {status}")
        return document

    @staticmethod
    def delete_document(db: Session, document_id: str, commit: bool = True) -> None:
        """
        Delete a document and its associated files.

        Args:
            db: Database session
            document_id: Document ID
            commit: Whether to commit immediately. Set False when composing a
                larger transaction.
        """
        document = DocumentService.get_document(db, document_id)

        # Delete files from S3
        try:
            # Extract object keys from URLs
            if document.source_file_url:
                # Parse object key from URL
                object_key = document.source_file_url.split(f"{settings.S3_BUCKET_NAME}/")[-1]
                s3_service.delete_file(object_key)

        except Exception as e:
            logger.warning(f"Failed to delete files for document {document_id}: {e}")

        # Delete document record (cascade will delete related records)
        db.delete(document)
        if commit:
            db.commit()
            logger.info(f"Deleted document {document_id}")
        else:
            logger.info(f"Staged document {document_id} for deletion")


document_service = DocumentService()
