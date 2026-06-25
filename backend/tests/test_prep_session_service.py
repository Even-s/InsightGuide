"""
Unit tests for Prep Session Service
Tests prep session management operations.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.models.document import Document
from app.models.interview_session import InterviewSession
from app.models.prep_session import PrepSession
from app.schemas.prep_session import PrepSessionCreate, PrepSessionUpdate
from app.services.prep_session_service import PrepSessionService, prep_session_service


class TestPrepSessionService:
    """Test suite for prep session service."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.refresh = Mock()
        db.add = Mock()
        db.delete = Mock()
        return db

    @pytest.fixture
    def sample_document(self):
        """Create a sample document."""
        return Document(
            id="doc-123",
            user_id="user-123",
            title="Test Document",
            status="analyzed",
            created_at=datetime.utcnow(),
        )

    @pytest.fixture
    def sample_prep_session(self):
        """Create a sample prep session."""
        return PrepSession(
            id="prep-123",
            document_id="doc-123",
            user_id="user-123",
            title="Test Prep Session",
            status="ready",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        assert prep_session_service is not None
        assert isinstance(prep_session_service, PrepSessionService)

    def test_get_prep_session_success(self, mock_db, sample_prep_session):
        """Test successful prep session retrieval."""
        mock_db.query().filter().first.return_value = sample_prep_session

        result = prep_session_service.get_prep_session(mock_db, "prep-123")

        assert result == sample_prep_session
        assert result.id == "prep-123"

    def test_get_prep_session_not_found(self, mock_db):
        """Test get prep session raises exception when not found."""
        mock_db.query().filter().first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            prep_session_service.get_prep_session(mock_db, "nonexistent")

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    def test_update_prep_session_title(self, mock_db, sample_prep_session):
        """Test updating prep session title."""
        mock_db.query().filter().first.return_value = sample_prep_session

        update_data = PrepSessionUpdate(title="Updated Title")

        result = prep_session_service.update_prep_session(
            db=mock_db, prep_session_id="prep-123", update_data=update_data
        )

        assert result.title == "Updated Title"
        assert result.updated_at is not None
        mock_db.commit.assert_called_once()

    def test_update_prep_session_status(self, mock_db, sample_prep_session):
        """Test updating prep session status."""
        mock_db.query().filter().first.return_value = sample_prep_session

        update_data = PrepSessionUpdate(status="archived")

        result = prep_session_service.update_prep_session(
            db=mock_db, prep_session_id="prep-123", update_data=update_data
        )

        assert result.status == "archived"
        mock_db.commit.assert_called_once()

    def test_update_prep_session_both(self, mock_db, sample_prep_session):
        """Test updating both title and status."""
        mock_db.query().filter().first.return_value = sample_prep_session

        update_data = PrepSessionUpdate(title="New Title", status="ready")

        result = prep_session_service.update_prep_session(
            db=mock_db, prep_session_id="prep-123", update_data=update_data
        )

        assert result.title == "New Title"
        assert result.status == "ready"

    def test_update_prep_session_not_found(self, mock_db):
        """Test update fails when prep session not found."""
        mock_db.query().filter().first.return_value = None

        update_data = PrepSessionUpdate(title="New Title")

        with pytest.raises(HTTPException) as exc_info:
            prep_session_service.update_prep_session(
                db=mock_db, prep_session_id="nonexistent", update_data=update_data
            )

        assert exc_info.value.status_code == 404

    @patch("app.services.document_service.document_service")
    def test_delete_prep_session_success(self, mock_doc_service, mock_db, sample_prep_session):
        """Test successful prep session deletion."""
        mock_db.query().filter().first.return_value = sample_prep_session
        mock_doc_service.delete_document.return_value = None

        prep_session_service.delete_prep_session(mock_db, "prep-123")

        mock_doc_service.delete_document.assert_called_once_with(mock_db, "doc-123", commit=False)
        mock_db.commit.assert_called_once()

    def test_delete_prep_session_not_found(self, mock_db):
        """Test delete fails when prep session not found."""
        mock_db.query().filter().first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            prep_session_service.delete_prep_session(mock_db, "nonexistent")

        assert exc_info.value.status_code == 404

    @patch("app.services.document_service.document_service")
    def test_delete_prep_session_rollback_on_error(
        self, mock_doc_service, mock_db, sample_prep_session
    ):
        """Test rollback when deletion fails."""
        mock_db.query().filter().first.return_value = sample_prep_session
        mock_doc_service.delete_document.side_effect = Exception("Delete failed")

        with pytest.raises(Exception):
            prep_session_service.delete_prep_session(mock_db, "prep-123")

        mock_db.rollback.assert_called_once()

    @patch("app.services.document_service.document_service")
    def test_delete_all_prep_sessions_success(self, mock_doc_service, mock_db):
        """Test deleting all prep sessions for a user."""
        prep_sessions = [
            PrepSession(id="prep-1", document_id="doc-1", user_id="user-123", status="ready"),
            PrepSession(id="prep-2", document_id="doc-2", user_id="user-123", status="ready"),
        ]

        mock_db.query().filter().all.return_value = prep_sessions

        prep_session_service.delete_all_prep_sessions(mock_db, "user-123")

        # Should delete both documents
        assert mock_doc_service.delete_document.call_count == 2
        mock_db.commit.assert_called_once()

    @patch("app.services.document_service.document_service")
    def test_delete_all_prep_sessions_empty(self, mock_doc_service, mock_db):
        """Test deleting when user has no prep sessions."""
        mock_db.query().filter().all.return_value = []

        prep_session_service.delete_all_prep_sessions(mock_db, "user-123")

        mock_doc_service.delete_document.assert_not_called()
        mock_db.commit.assert_called_once()

    def test_list_prep_sessions_basic(self, mock_db):
        """Test listing prep sessions without filters."""
        # Create a mock prep session that behaves like an ORM object
        mock_session = Mock()
        mock_session.id = "prep-123"
        mock_session.document_id = "doc-123"
        mock_session.user_id = "user-123"
        mock_session.title = "Test Prep Session"
        mock_session.status = "ready"
        mock_session.created_at = datetime.utcnow()
        mock_session.updated_at = datetime.utcnow()
        mock_session.document = Mock()
        mock_session.document.title = "Test Document"

        mock_db.query().join().filter().count.return_value = 1
        mock_db.query().join().filter().order_by().offset().limit().all.return_value = [
            mock_session
        ]
        mock_db.query().filter().scalar.return_value = 5

        with patch("app.services.prep_session_service.billing_service") as mock_billing:
            mock_billing.summarize_documents.return_value = {
                "doc-123": {"totalCostUsd": 1.50, "inputTokens": 1000, "outputTokens": 500}
            }
            mock_billing.empty_summary.return_value = {
                "totalCostUsd": 0.0,
                "inputTokens": 0,
                "outputTokens": 0,
            }

            result = prep_session_service.list_prep_sessions(db=mock_db, user_id="user-123")

        assert result.total == 1
        assert len(result.prepSessions) == 1

    def test_list_prep_sessions_with_status_filter(self, mock_db):
        """Test listing prep sessions with status filter."""
        mock_db.query().join().filter().filter().count.return_value = 0
        mock_db.query().join().filter().filter().order_by().offset().limit().all.return_value = []

        with patch("app.services.prep_session_service.billing_service"):
            result = prep_session_service.list_prep_sessions(
                db=mock_db, user_id="user-123", status_filter="ready"
            )

        assert result.total == 0

    def test_list_prep_sessions_pagination(self, mock_db):
        """Test prep session pagination."""
        mock_db.query().join().filter().count.return_value = 100
        mock_db.query().join().filter().order_by().offset().limit().all.return_value = []

        with patch("app.services.prep_session_service.billing_service"):
            result = prep_session_service.list_prep_sessions(
                db=mock_db, user_id="user-123", limit=10, offset=20
            )

        assert result.total == 100
        assert result.limit == 10
        assert result.offset == 20

    def test_list_prep_sessions_sorting_asc(self, mock_db):
        """Test sorting prep sessions ascending."""
        mock_db.query().join().filter().count.return_value = 0
        mock_db.query().join().filter().order_by().offset().limit().all.return_value = []

        with patch("app.services.prep_session_service.billing_service"):
            result = prep_session_service.list_prep_sessions(
                db=mock_db, user_id="user-123", sort_by="createdAt", order="asc"
            )

        assert result is not None

    def test_list_prep_sessions_sorting_desc(self, mock_db):
        """Test sorting prep sessions descending."""
        mock_db.query().join().filter().count.return_value = 0
        mock_db.query().join().filter().order_by().offset().limit().all.return_value = []

        with patch("app.services.prep_session_service.billing_service"):
            result = prep_session_service.list_prep_sessions(
                db=mock_db, user_id="user-123", sort_by="updatedAt", order="desc"
            )

        assert result is not None

    def test_get_sort_field_mapping(self):
        """Test sort field name mapping."""
        assert prep_session_service._get_sort_field("createdAt") == "created_at"
        assert prep_session_service._get_sort_field("updatedAt") == "updated_at"
        assert prep_session_service._get_sort_field("status") == "status"
        assert prep_session_service._get_sort_field("unknown") == "created_at"

    def test_get_prep_session_interview_sessions(self, mock_db, sample_prep_session):
        """Test getting presentation sessions for a prep session."""
        mock_db.query().filter().first.return_value = sample_prep_session

        sessions = [
            InterviewSession(id="session-1", prep_session_id="prep-123"),
            InterviewSession(id="session-2", prep_session_id="prep-123"),
        ]
        mock_db.query().filter().order_by().all.return_value = sessions

        result = prep_session_service.get_prep_session_interview_sessions(
            db=mock_db, prep_session_id="prep-123"
        )

        assert len(result) == 2
        assert result[0].id == "session-1"

    def test_get_prep_session_interview_sessions_empty(self, mock_db, sample_prep_session):
        """Test getting presentation sessions when none exist."""
        mock_db.query().filter().first.return_value = sample_prep_session
        mock_db.query().filter().order_by().all.return_value = []

        result = prep_session_service.get_prep_session_interview_sessions(
            db=mock_db, prep_session_id="prep-123"
        )

        assert len(result) == 0

    def test_get_prep_session_interview_sessions_not_found(self, mock_db):
        """Test getting sessions for nonexistent prep session."""
        mock_db.query().filter().first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            prep_session_service.get_prep_session_interview_sessions(
                db=mock_db, prep_session_id="nonexistent"
            )

        assert exc_info.value.status_code == 404
