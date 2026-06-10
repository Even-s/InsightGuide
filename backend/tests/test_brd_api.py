"""
Integration tests for BRD API routes
Tests all BRD endpoints including generation, retrieval, and export.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime

from app.main import app
from app.models.brd import BRDDraft, Requirement, BRDStatus, RequirementType, RequirementPriority
from app.models.user import User


client = TestClient(app)


class TestBRDAPI:
    """Test suite for BRD API endpoints."""

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user for authentication."""
        return User(
            id="user-123",
            email="test@example.com",
            full_name="Test User"
        )

    @pytest.fixture
    def sample_brd(self, mock_current_user):
        """Create a sample BRD draft."""
        return BRDDraft(
            id="brd-123",
            interview_session_id="session-456",
            user_id=mock_current_user.id,
            status=BRDStatus.COMPLETED,
            title="Test BRD",
            executive_summary="Test summary",
            business_objectives=["Objective 1"],
            generated_at=datetime.utcnow(),
            markdown_content="# Test BRD\n\nTest content"
        )

    @pytest.fixture
    def sample_requirements(self):
        """Create sample requirements."""
        return [
            Requirement(
                id="req-1",
                brd_draft_id="brd-123",
                title="Test Requirement",
                description="Test description",
                type=RequirementType.FUNCTIONAL,
                priority=RequirementPriority.MUST_HAVE
            )
        ]

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_generate_brd(self, mock_get_db, mock_get_current_user, mock_current_user):
        """Test POST /api/brd/generate endpoint."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        with patch('app.services.brd_generator_service.brd_generator_service.generate_brd') as mock_gen:
            mock_gen.return_value = BRDDraft(
                id="new-brd",
                interview_session_id="session-456",
                user_id=mock_current_user.id,
                status=BRDStatus.GENERATING
            )

            response = client.post(
                "/api/brd/generate",
                json={"interview_session_id": "session-456"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "brd_id" in data
        assert data["status"] == "generating"

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_get_brd_by_id(self, mock_get_db, mock_get_current_user, mock_current_user, sample_brd):
        """Test GET /api/brd/{brd_id} endpoint."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_db.query().filter().first.return_value = sample_brd
        mock_get_db.return_value = mock_db

        response = client.get(f"/api/brd/{sample_brd.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_brd.id
        assert data["title"] == sample_brd.title

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_get_brd_not_found(self, mock_get_db, mock_get_current_user, mock_current_user):
        """Test GET /api/brd/{brd_id} with non-existent ID."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_db.query().filter().first.return_value = None
        mock_get_db.return_value = mock_db

        response = client.get("/api/brd/nonexistent-id")

        assert response.status_code == 404

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_get_brd_by_session(self, mock_get_db, mock_get_current_user, mock_current_user, sample_brd):
        """Test GET /api/brd/session/{session_id} endpoint."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_db.query().filter().first.return_value = sample_brd
        mock_get_db.return_value = mock_db

        response = client.get(f"/api/brd/session/{sample_brd.interview_session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["interview_session_id"] == sample_brd.interview_session_id

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_export_brd_markdown(self, mock_get_db, mock_get_current_user, mock_current_user, sample_brd):
        """Test POST /api/brd/{brd_id}/export endpoint for markdown."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_db.query().filter().first.return_value = sample_brd
        mock_get_db.return_value = mock_db

        response = client.post(
            f"/api/brd/{sample_brd.id}/export",
            json={"format": "markdown"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "markdown"
        assert "download_url" in data

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_export_brd_pdf(self, mock_get_db, mock_get_current_user, mock_current_user, sample_brd):
        """Test POST /api/brd/{brd_id}/export endpoint for PDF."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_db.query().filter().first.return_value = sample_brd
        mock_get_db.return_value = mock_db

        response = client.post(
            f"/api/brd/{sample_brd.id}/export",
            json={"format": "pdf"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "pdf"
        assert "download_url" in data
        assert "pdf" in data["download_url"]

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_export_brd_unsupported_format(self, mock_get_db, mock_get_current_user, mock_current_user, sample_brd):
        """Test export with unsupported format."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_db.query().filter().first.return_value = sample_brd
        mock_get_db.return_value = mock_db

        response = client.post(
            f"/api/brd/{sample_brd.id}/export",
            json={"format": "docx"}
        )

        assert response.status_code == 400

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_download_markdown(self, mock_get_db, mock_get_current_user, mock_current_user, sample_brd):
        """Test GET /api/brd/{brd_id}/download/markdown endpoint."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_db.query().filter().first.return_value = sample_brd
        mock_get_db.return_value = mock_db

        response = client.get(f"/api/brd/{sample_brd.id}/download/markdown")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"
        assert "attachment" in response.headers.get("content-disposition", "")

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_download_pdf(self, mock_get_db, mock_get_current_user, mock_current_user, sample_brd):
        """Test GET /api/brd/{brd_id}/download/pdf endpoint."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_db.query().filter().first.return_value = sample_brd
        mock_get_db.return_value = mock_db

        with patch('app.services.brd_pdf_export_service.brd_pdf_export_service.generate_pdf') as mock_pdf:
            from io import BytesIO
            mock_pdf.return_value = BytesIO(b'%PDF-1.4 test')

            response = client.get(f"/api/brd/{sample_brd.id}/download/pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_get_requirements(self, mock_get_db, mock_get_current_user, mock_current_user, sample_brd, sample_requirements):
        """Test GET /api/brd/{brd_id}/requirements endpoint."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_db.query().filter().first.return_value = sample_brd
        mock_db.query().filter().all.return_value = sample_requirements
        mock_get_db.return_value = mock_db

        response = client.get(f"/api/brd/{sample_brd.id}/requirements")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_update_requirement(self, mock_get_db, mock_get_current_user, mock_current_user, sample_brd, sample_requirements):
        """Test PATCH /api/brd/{brd_id}/requirements/{requirement_id} endpoint."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_db.query().filter().first.side_effect = [sample_brd, sample_requirements[0]]
        mock_get_db.return_value = mock_db

        update_data = {
            "title": "Updated Title",
            "priority": "should_have"
        }

        response = client.patch(
            f"/api/brd/{sample_brd.id}/requirements/req-1",
            json=update_data
        )

        assert response.status_code == 200

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_delete_requirement(self, mock_get_db, mock_get_current_user, mock_current_user, sample_brd, sample_requirements):
        """Test DELETE /api/brd/{brd_id}/requirements/{requirement_id} endpoint."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_db.query().filter().first.side_effect = [sample_brd, sample_requirements[0]]
        mock_get_db.return_value = mock_db

        response = client.delete(f"/api/brd/{sample_brd.id}/requirements/req-1")

        assert response.status_code == 200

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_generate_brd_invalid_session(self, mock_get_db, mock_get_current_user, mock_current_user):
        """Test BRD generation with invalid session ID."""
        mock_get_current_user.return_value = mock_current_user
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        response = client.post(
            "/api/brd/generate",
            json={"interview_session_id": ""}
        )

        assert response.status_code == 422  # Validation error

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_export_brd_not_completed(self, mock_get_db, mock_get_current_user, mock_current_user):
        """Test export when BRD is still generating."""
        mock_get_current_user.return_value = mock_current_user

        generating_brd = BRDDraft(
            id="gen-brd",
            interview_session_id="session-1",
            user_id=mock_current_user.id,
            status=BRDStatus.GENERATING
        )

        mock_db = Mock()
        mock_db.query().filter().first.return_value = generating_brd
        mock_get_db.return_value = mock_db

        response = client.post(
            f"/api/brd/{generating_brd.id}/export",
            json={"format": "markdown"}
        )

        assert response.status_code == 400

    def test_unauthorized_access(self):
        """Test that endpoints require authentication."""
        # Without authentication mock, should fail
        response = client.get("/api/brd/some-id")
        assert response.status_code in [401, 403, 422]

    @patch('app.api.deps.get_current_user')
    @patch('app.api.deps.get_db')
    def test_user_isolation(self, mock_get_db, mock_get_current_user):
        """Test that users can only access their own BRDs."""
        user1 = User(id="user-1", email="user1@example.com", full_name="User 1")
        user2_brd = BRDDraft(
            id="brd-user2",
            interview_session_id="session-2",
            user_id="user-2",  # Different user
            status=BRDStatus.COMPLETED
        )

        mock_get_current_user.return_value = user1
        mock_db = Mock()
        mock_db.query().filter().first.return_value = None  # User 1 can't see user 2's BRD
        mock_get_db.return_value = mock_db

        response = client.get("/api/brd/brd-user2")

        assert response.status_code == 404
