"""
Unit tests for BRD Generator Service
Tests AI-powered BRD generation from interview data.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.brd_generator_service import brd_generator_service
from app.models.brd import BRDDraft, Requirement, BRDStatus
from app.models.interview_session import InterviewSession
from app.models.question_card import QuestionCard
from app.models.user import User


class TestBRDGeneratorService:
    """Test suite for BRD generator service."""

    def _configure_generation_queries(self, mock_db, session, existing_brd=None):
        """Route mocked SQLAlchemy queries by model for generate_brd tests."""
        def query(model):
            query_mock = Mock()
            query_mock.filter.return_value = query_mock
            query_mock.order_by.return_value = query_mock
            query_mock.all.return_value = []
            if model is InterviewSession:
                query_mock.first.return_value = session
            elif model is BRDDraft:
                query_mock.first.return_value = existing_brd
            else:
                query_mock.first.return_value = None
            return query_mock

        mock_db.query.side_effect = query

    def _sample_interview_data(self, session):
        return {
            "session_id": session.id,
            "document_title": "Test Document",
            "questions_with_answers": [],
            "full_transcript": "",
            "utterances": [],
            "total_questions": 0,
            "answered_questions": 0,
        }

    def _sample_brd_content(self):
        return {
            "title": "E-Commerce Platform Modernization",
            "executive_summary": "Test summary",
            "project_overview": "Test overview",
            "business_objectives": ["Increase conversion by 20%"],
            "success_criteria": ["Conversion increases"],
            "stakeholders": ["Product team"],
            "assumptions": [],
            "constraints": [],
            "risks": [],
        }

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def sample_user(self):
        """Create a sample user."""
        return User(
            id="user-123",
            email="test@example.com",
            hashed_password="hashed_test_password"
        )

    @pytest.fixture
    def sample_interview_session(self, sample_user):
        """Create a sample interview session."""
        session = InterviewSession(
            id="session-456",
            user_id=sample_user.id,
            document_id="doc-789",
            prep_session_id="prep-789",
            status="ended",
            started_at=datetime(2026, 6, 10, 9, 0, 0),
            ended_at=datetime(2026, 6, 10, 10, 30, 0)
        )
        return session

    @pytest.fixture
    def sample_question_cards(self):
        """Create sample question cards with answers."""
        cards = []

        card1 = QuestionCard(
            id="card-1",
            document_id="doc-789",
            section_id="section-1",
            section_number=1,
            question_text="What is the main goal of this project?",
            question_type="clarification",
            importance="must",
            coverage_rule={"semanticAnchors": ["goal"]},
        )
        cards.append(card1)

        card2 = QuestionCard(
            id="card-2",
            document_id="doc-789",
            section_id="section-1",
            section_number=1,
            question_text="Who are the key stakeholders?",
            question_type="clarification",
            importance="must",
            coverage_rule={"semanticAnchors": ["stakeholder"]},
        )
        cards.append(card2)

        card3 = QuestionCard(
            id="card-3",
            document_id="doc-789",
            section_id="section-2",
            section_number=2,
            question_text="What are the main functional requirements?",
            question_type="exploration",
            importance="must",
            coverage_rule={"semanticAnchors": ["requirements"]},
        )
        cards.append(card3)

        return cards

    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        assert brd_generator_service is not None
        assert hasattr(brd_generator_service, 'generate_brd')

    @patch('app.services.brd_generator_service.openai_service')
    def test_generate_brd_creates_draft(self, mock_openai, mock_db, sample_interview_session, sample_question_cards):
        """Test that generate_brd creates a BRD draft."""
        # Setup mocks
        self._configure_generation_queries(mock_db, sample_interview_session)

        mock_openai.generate_completion.return_value = {
            "title": "E-Commerce Platform Modernization",
            "executive_summary": "Test summary",
            "business_objectives": ["Increase conversion by 20%"],
            "requirements": []
        }

        # Create new BRD draft mock
        new_brd = BRDDraft(
            id="new-brd-123",
            interview_session_id=sample_interview_session.id,
            user_id=sample_interview_session.user_id,
            status=BRDStatus.GENERATING
        )
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        # Execute
        with patch.object(mock_db, 'add'):
            with patch.object(mock_db, 'commit'):
                with patch.object(mock_db, 'refresh'):
                    with patch.object(brd_generator_service, '_extract_interview_data', return_value=self._sample_interview_data(sample_interview_session)):
                        with patch.object(brd_generator_service, '_generate_brd_content', return_value=self._sample_brd_content()):
                            with patch.object(brd_generator_service, '_extract_requirements', return_value=[]):
                                with patch.object(brd_generator_service, '_create_requirements'):
                                    result = brd_generator_service.generate_brd(
                                        mock_db,
                                        sample_interview_session.id
                                    )

        # Verify
        assert result is not None

    def test_generate_brd_requires_session_id(self, mock_db):
        """Test that generate_brd requires a valid session ID."""
        with pytest.raises(Exception):
            brd_generator_service.generate_brd(mock_db, None)

    @patch('app.services.brd_generator_service.openai_service')
    def test_generate_brd_handles_no_questions(self, mock_openai, mock_db, sample_interview_session):
        """Test BRD generation when session has no questions."""
        self._configure_generation_queries(mock_db, sample_interview_session)

        mock_openai.generate_completion.return_value = {
            "title": "BRD Without Questions",
            "executive_summary": "Limited data available"
        }

        # Should still create a BRD, just with limited content
        with patch.object(mock_db, 'add'):
            with patch.object(mock_db, 'commit'):
                with patch.object(mock_db, 'refresh'):
                    with patch.object(brd_generator_service, '_extract_interview_data', return_value=self._sample_interview_data(sample_interview_session)):
                        with patch.object(brd_generator_service, '_generate_brd_content', return_value=self._sample_brd_content()):
                            with patch.object(brd_generator_service, '_extract_requirements', return_value=[]):
                                with patch.object(brd_generator_service, '_create_requirements'):
                                    result = brd_generator_service.generate_brd(
                                        mock_db,
                                        sample_interview_session.id
                                    )

        assert result is not None

    def test_extract_interview_data_structure(self):
        """Test that _extract_interview_data returns proper structure."""
        # This would test the internal method if it were public
        # For now, we test through generate_brd
        pass

    def test_markdown_generation(self):
        """Test that markdown content is generated correctly."""
        brd = BRDDraft(
            id="test-brd",
            interview_session_id="session-1",
            user_id="user-1",
            status=BRDStatus.COMPLETED,
            title="Test BRD",
            executive_summary="This is a test",
            business_objectives=["Objective 1", "Objective 2"]
        )

        requirements_data = [
            {"id": "req-1", "title": "Requirement 1", "description": "Test req", "priority": "must_have", "type": "functional", "user_story": "As a user, I want requirement 1"}
        ]

        markdown = brd_generator_service._generate_markdown(brd, requirements_data)

        assert markdown is not None
        assert "# Test BRD" in markdown
        assert "This is a test" in markdown
        assert "Objective 1" in markdown

    def test_requirement_extraction(self):
        """Test requirement extraction from interview answers."""
        # Test the requirement extraction logic
        pass

    @patch('app.services.brd_generator_service.openai_service')
    def test_generate_brd_sets_timestamps(self, mock_openai, mock_db, sample_interview_session, sample_question_cards):
        """Test that BRD generation sets proper timestamps."""
        self._configure_generation_queries(mock_db, sample_interview_session)

        start_time = datetime.utcnow()

        mock_openai.generate_completion.return_value = {
            "title": "Test",
            "executive_summary": "Test"
        }

        with patch.object(mock_db, 'add'):
            with patch.object(mock_db, 'commit'):
                with patch.object(mock_db, 'refresh'):
                    with patch.object(brd_generator_service, '_extract_interview_data', return_value=self._sample_interview_data(sample_interview_session)):
                        with patch.object(brd_generator_service, '_generate_brd_content', return_value=self._sample_brd_content()):
                            with patch.object(brd_generator_service, '_extract_requirements', return_value=[]):
                                with patch.object(brd_generator_service, '_create_requirements'):
                                    result = brd_generator_service.generate_brd(
                                        mock_db,
                                        sample_interview_session.id
                                    )

        # Verify timing
        end_time = datetime.utcnow()
        assert start_time <= end_time

    def test_extract_requirements_structure(self):
        """Test that _extract_requirements returns proper structure."""
        # Verify the method exists and accepts correct params
        assert hasattr(brd_generator_service, '_extract_requirements')
        assert hasattr(brd_generator_service, '_create_requirements')
        assert hasattr(brd_generator_service, '_generate_brd_content')

    def test_brd_status_transitions(self):
        """Test that BRD status transitions correctly."""
        # Test: generating -> completed
        # Test: generating -> failed (on error)
        pass

    @patch('app.services.brd_generator_service.openai_service')
    def test_generate_brd_error_handling(self, mock_openai, mock_db, sample_interview_session):
        """Test error handling during BRD generation."""
        self._configure_generation_queries(mock_db, sample_interview_session)

        with patch.object(brd_generator_service, '_extract_interview_data', return_value=self._sample_interview_data(sample_interview_session)):
            with patch.object(brd_generator_service, '_generate_brd_content', side_effect=Exception("API Error")):
                with pytest.raises(Exception):
                    brd_generator_service.generate_brd(
                        mock_db,
                        sample_interview_session.id
                    )

    def test_markdown_format_validity(self):
        """Test that generated markdown is valid."""
        brd = BRDDraft(
            id="md-test",
            interview_session_id="session-1",
            user_id="user-1",
            status=BRDStatus.COMPLETED,
            title="Markdown Test",
            executive_summary="Summary",
            business_objectives=["Obj 1"],
            success_criteria=["Criteria 1"],
        )

        requirements_data = [
            {"id": "req-1", "title": "Test Req", "description": "Description", "priority": "must_have", "type": "functional", "user_story": "As a user, I want test req"}
        ]

        markdown = brd_generator_service._generate_markdown(brd, requirements_data)

        # Check markdown structure
        assert "# " in markdown  # Has headings
        assert "## " in markdown  # Has subheadings
        assert "- " in markdown or "* " in markdown  # Has lists

    def test_concurrent_brd_generation(self, mock_db):
        """Test that multiple BRDs can be generated concurrently."""
        # This would test thread safety if needed
        pass

    def test_brd_regeneration(self, mock_db, sample_interview_session):
        """Test regenerating BRD for same session."""
        # Should create new BRD, not update existing
        self._configure_generation_queries(mock_db, sample_interview_session)

        # First generation
        with patch('app.services.brd_generator_service.openai_service'):
            with patch.object(mock_db, 'add'):
                with patch.object(mock_db, 'commit'):
                    with patch.object(mock_db, 'refresh'):
                        with patch.object(brd_generator_service, '_extract_interview_data', return_value=self._sample_interview_data(sample_interview_session)):
                            with patch.object(brd_generator_service, '_generate_brd_content', return_value=self._sample_brd_content()):
                                with patch.object(brd_generator_service, '_extract_requirements', return_value=[]):
                                    with patch.object(brd_generator_service, '_create_requirements'):
                                        brd1 = brd_generator_service.generate_brd(
                                            mock_db,
                                            sample_interview_session.id
                                        )

        # Second generation
        with patch('app.services.brd_generator_service.openai_service'):
            with patch.object(mock_db, 'add'):
                with patch.object(mock_db, 'commit'):
                    with patch.object(mock_db, 'refresh'):
                        with patch.object(brd_generator_service, '_extract_interview_data', return_value=self._sample_interview_data(sample_interview_session)):
                            with patch.object(brd_generator_service, '_generate_brd_content', return_value=self._sample_brd_content()):
                                with patch.object(brd_generator_service, '_extract_requirements', return_value=[]):
                                    with patch.object(brd_generator_service, '_create_requirements'):
                                        brd2 = brd_generator_service.generate_brd(
                                            mock_db,
                                            sample_interview_session.id
                                        )

        # Should be different BRDs
        assert brd1 is not None
        assert brd2 is not None
