"""
Unit tests for Interview Service
Tests interview session management, card states, and utterance handling.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.models.document import Document
from app.models.interview_session import InterviewCardState, InterviewSession
from app.models.prep_session import PrepSession
from app.models.question_card import QuestionCard
from app.models.utterance import Utterance
from app.schemas.interview import (
    InterviewCardStateUpdate,
    InterviewSessionCreate,
    InterviewSessionUpdate,
)
from app.services.interview_service import InterviewService, interview_service


class TestInterviewService:
    """Test suite for interview service."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.refresh = Mock()
        db.add = Mock()
        db.delete = Mock()
        db.query.return_value.filter.return_value.all.return_value = []
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
        )

    @pytest.fixture
    def sample_interview_session(self):
        """Create a sample interview session."""
        return InterviewSession(
            id="session-123",
            prep_session_id="prep-123",
            document_id="doc-123",
            user_id="user-123",
            status="idle",
            created_at=datetime.utcnow(),
        )

    @pytest.fixture
    def sample_question_cards(self):
        """Create sample question cards."""
        return [
            QuestionCard(
                id="card-1",
                document_id="doc-123",
                section_id="section-1",
                question_text="What are the objectives?",
                importance="must",
            ),
            QuestionCard(
                id="card-2",
                document_id="doc-123",
                section_id="section-1",
                question_text="Who are the stakeholders?",
                importance="should",
            ),
        ]

    @pytest.fixture
    def sample_card_state(self):
        """Create a sample card state."""
        return InterviewCardState(
            id="state-123",
            session_id="session-123",
            question_card_id="card-1",
            status="pending",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        assert interview_service is not None
        assert isinstance(interview_service, InterviewService)

    def test_calculate_active_duration_not_started(self, sample_interview_session):
        """Test duration calculation when session not started."""
        sample_interview_session.started_at = None

        duration = interview_service.calculate_active_duration(sample_interview_session)

        assert duration is None

    def test_calculate_active_duration_no_pauses(self, sample_interview_session):
        """Test duration calculation with no pauses."""
        now = datetime.utcnow()
        sample_interview_session.started_at = now - timedelta(minutes=30)
        sample_interview_session.ended_at = now
        sample_interview_session.paused_duration_seconds = 0
        sample_interview_session.paused_at = None

        duration = interview_service.calculate_active_duration(sample_interview_session)

        assert duration == pytest.approx(1800, abs=2)  # 30 minutes

    def test_calculate_active_duration_with_pauses(self, sample_interview_session):
        """Test duration calculation with pause time."""
        now = datetime.utcnow()
        sample_interview_session.started_at = now - timedelta(minutes=30)
        sample_interview_session.ended_at = now
        sample_interview_session.paused_duration_seconds = 600  # 10 minutes paused
        sample_interview_session.paused_at = None

        duration = interview_service.calculate_active_duration(sample_interview_session)

        assert duration == pytest.approx(1200, abs=2)  # 20 minutes active

    def test_calculate_active_duration_currently_paused(self, sample_interview_session):
        """Test duration calculation when currently paused."""
        now = datetime.utcnow()
        sample_interview_session.started_at = now - timedelta(minutes=30)
        sample_interview_session.ended_at = None
        sample_interview_session.paused_duration_seconds = 0
        sample_interview_session.paused_at = now - timedelta(minutes=5)

        duration = interview_service.calculate_active_duration(sample_interview_session)

        # Should exclude the current 5-minute pause
        assert duration == pytest.approx(1500, abs=2)  # 25 minutes

    def test_end_current_pause_not_paused(self, sample_interview_session):
        """Test ending pause when not paused."""
        sample_interview_session.paused_at = None
        sample_interview_session.paused_duration_seconds = 0

        interview_service._end_current_pause(sample_interview_session, datetime.utcnow())

        assert sample_interview_session.paused_at is None
        assert sample_interview_session.paused_duration_seconds == 0

    def test_end_current_pause_accumulates_duration(self, sample_interview_session):
        """Test that pause duration accumulates correctly."""
        now = datetime.utcnow()
        sample_interview_session.paused_at = now - timedelta(minutes=5)
        sample_interview_session.paused_duration_seconds = 300  # 5 minutes from before

        interview_service._end_current_pause(sample_interview_session, now)

        # Should add 5 more minutes
        assert sample_interview_session.paused_duration_seconds == pytest.approx(600, abs=2)
        assert sample_interview_session.paused_at is None

    @patch("app.services.interview_service.uuid")
    def test_create_session_success(
        self, mock_uuid, mock_db, sample_document, sample_prep_session, sample_question_cards
    ):
        """Test successful interview session creation."""
        mock_uuid.uuid4().hex = "abc123"

        # Setup mocks
        mock_db.query().filter().first.side_effect = [
            sample_prep_session,  # First call for prep session
            sample_document,  # Second call for document
            None,  # Third call for recent session check
        ]
        mock_db.query().filter().with_for_update().first.return_value = sample_prep_session
        mock_db.query().filter().order_by().first.return_value = None  # No recent session
        mock_db.query().filter().all.side_effect = [
            [],  # No active sessions to end
            sample_question_cards,  # Question cards for initialization
        ]

        session_data = InterviewSessionCreate(prepSessionId="prep-123", documentId="doc-123")

        session = interview_service.create_session(
            db=mock_db, user_id="user-123", session_data=session_data
        )

        # Verify session was added
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_create_session_prep_session_not_found(self, mock_db):
        """Test create session fails when prep session not found."""
        mock_db.query().filter().first.return_value = None

        session_data = InterviewSessionCreate(prepSessionId="nonexistent", documentId="doc-123")

        with pytest.raises(HTTPException) as exc_info:
            interview_service.create_session(
                db=mock_db, user_id="user-123", session_data=session_data
            )

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    def test_create_session_wrong_user(self, mock_db, sample_prep_session):
        """Test create session fails for wrong user."""
        mock_db.query().filter().first.return_value = sample_prep_session

        session_data = InterviewSessionCreate(prepSessionId="prep-123", documentId="doc-123")

        with pytest.raises(HTTPException) as exc_info:
            interview_service.create_session(
                db=mock_db, user_id="different-user", session_data=session_data
            )

        assert exc_info.value.status_code == 403
        assert "permission" in str(exc_info.value.detail).lower()

    def test_create_session_prep_not_ready(self, mock_db, sample_prep_session):
        """Test create session fails when prep session not ready."""
        sample_prep_session.status = "preparing"
        mock_db.query().filter().first.return_value = sample_prep_session

        session_data = InterviewSessionCreate(prepSessionId="prep-123", documentId="doc-123")

        with pytest.raises(HTTPException) as exc_info:
            interview_service.create_session(
                db=mock_db, user_id="user-123", session_data=session_data
            )

        assert exc_info.value.status_code == 400
        assert "ready" in str(exc_info.value.detail).lower()

    def test_create_session_document_not_analyzed(
        self, mock_db, sample_prep_session, sample_document
    ):
        """Test create session fails when document not analyzed."""
        sample_document.status = "analyzing"
        mock_db.query().filter().first.side_effect = [sample_prep_session, sample_document]

        session_data = InterviewSessionCreate(prepSessionId="prep-123", documentId="doc-123")

        with pytest.raises(HTTPException) as exc_info:
            interview_service.create_session(
                db=mock_db, user_id="user-123", session_data=session_data
            )

        assert exc_info.value.status_code == 400
        assert "analyzed" in str(exc_info.value.detail).lower()

    def test_get_session_success(self, mock_db, sample_interview_session):
        """Test successful session retrieval."""
        mock_db.query().filter().first.return_value = sample_interview_session

        session = interview_service.get_session(mock_db, "session-123")

        assert session == sample_interview_session

    def test_get_session_not_found(self, mock_db):
        """Test get session raises exception when not found."""
        mock_db.query().filter().first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            interview_service.get_session(mock_db, "nonexistent")

        assert exc_info.value.status_code == 404

    def test_update_session_status_to_interviewing(self, mock_db, sample_interview_session):
        """Test updating session status to interviewing."""
        mock_db.query().filter().first.return_value = sample_interview_session

        update_data = InterviewSessionUpdate(status="interviewing")

        with patch.object(interview_service, "_reset_card_progress_for_new_round") as reset:
            session = interview_service.update_session(
                db=mock_db, session_id="session-123", update_data=update_data
            )

        assert session.status == "interviewing"
        assert session.started_at is not None
        reset.assert_called_once_with(mock_db, sample_interview_session)
        mock_db.commit.assert_called_once()

    def test_reset_card_progress_for_new_round_clears_stale_state(
        self,
        mock_db,
        sample_interview_session,
        sample_card_state,
    ):
        sample_card_state.status = "listening"
        sample_card_state.confidence = 1.0
        sample_card_state.activation_score = 1.0
        sample_card_state.completion_score = 1.0
        sample_card_state.completion_source = "manual"
        sample_card_state.answered_at = datetime.utcnow()
        sample_card_state.evidence_transcript = "stale transcript"
        sample_card_state.evidence = {"satisfiedCriteria": ["criterion_0"]}
        sample_interview_session.active_card_id = "card-1"
        sample_interview_session.active_card_hint_id = "card-1"
        sample_interview_session.pending_answer_buffer = ["utt-1"]
        mock_db.query.return_value.filter.return_value.all.return_value = [sample_card_state]

        interview_service._reset_card_progress_for_new_round(
            mock_db,
            sample_interview_session,
        )

        assert sample_card_state.status == "pending"
        assert sample_card_state.confidence is None
        assert sample_card_state.activation_score == 0
        assert sample_card_state.completion_score == 0
        assert sample_card_state.completion_source is None
        assert sample_card_state.answered_at is None
        assert sample_card_state.evidence_transcript is None
        assert sample_card_state.evidence is None
        assert sample_interview_session.active_card_id is None
        assert sample_interview_session.active_card_hint_id is None
        assert sample_interview_session.pending_answer_buffer is None

    def test_update_session_status_to_paused(self, mock_db, sample_interview_session):
        """Test updating session status to paused."""
        now = datetime.utcnow()
        sample_interview_session.status = "interviewing"
        sample_interview_session.started_at = now - timedelta(minutes=10)
        mock_db.query().filter().first.return_value = sample_interview_session

        update_data = InterviewSessionUpdate(status="paused")

        session = interview_service.update_session(
            db=mock_db, session_id="session-123", update_data=update_data
        )

        assert session.status == "paused"
        assert session.paused_at is not None

    def test_update_session_status_to_ended(self, mock_db, sample_interview_session):
        """Test updating session status to ended."""
        now = datetime.utcnow()
        sample_interview_session.status = "interviewing"
        sample_interview_session.started_at = now - timedelta(minutes=30)
        mock_db.query().filter().first.return_value = sample_interview_session

        update_data = InterviewSessionUpdate(status="ended")

        session = interview_service.update_session(
            db=mock_db, session_id="session-123", update_data=update_data
        )

        assert session.status == "ended"
        assert session.ended_at is not None

    def test_update_session_resume_from_pause(self, mock_db, sample_interview_session):
        """Test resuming interview from paused state."""
        now = datetime.utcnow()
        sample_interview_session.status = "paused"
        sample_interview_session.started_at = now - timedelta(minutes=30)
        sample_interview_session.paused_at = now - timedelta(minutes=5)
        sample_interview_session.paused_duration_seconds = 0
        mock_db.query().filter().first.return_value = sample_interview_session

        update_data = InterviewSessionUpdate(status="interviewing")

        with patch.object(interview_service, "_reset_card_progress_for_new_round") as reset:
            session = interview_service.update_session(
                db=mock_db, session_id="session-123", update_data=update_data
            )

        assert session.status == "interviewing"
        reset.assert_not_called()
        # Pause duration should be accumulated
        assert session.paused_duration_seconds > 0
        assert session.paused_at is None

    def test_update_session_change_section(self, mock_db, sample_interview_session):
        """Test changing current section."""
        mock_db.query().filter().first.return_value = sample_interview_session
        mock_db.query().filter().filter().all.return_value = []  # No must cards

        update_data = InterviewSessionUpdate(currentSectionId="section-2")

        session = interview_service.update_session(
            db=mock_db, session_id="session-123", update_data=update_data
        )

        assert session.current_section_id == "section-2"

    def test_mark_missed_must_cards_at_risk(
        self, mock_db, sample_question_cards, sample_card_state
    ):
        """Test marking must-ask cards as at_risk when leaving section."""
        # First call returns question_cards, second returns card_states
        sample_card_state.status = "pending"
        mock_db.query.return_value.filter.return_value.filter.return_value.all.side_effect = [
            [sample_question_cards[0]],  # QuestionCard query
            [sample_card_state],  # InterviewCardState query
        ]
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [sample_question_cards[0]],
            [sample_card_state],
        ]

        interview_service._mark_missed_must_cards_at_risk(
            db=mock_db, session_id="session-123", section_id="section-1"
        )

        # Card state should be updated
        assert sample_card_state.status == "at_risk"
        mock_db.commit.assert_called()

    def test_update_card_state_success(self, mock_db, sample_interview_session, sample_card_state):
        """Test updating a card state."""
        mock_db.query().filter().first.side_effect = [sample_interview_session, sample_card_state]

        update_data = InterviewCardStateUpdate(
            status="sufficient",
            confidence=0.9,
            evidenceTranscript="Complete answer provided",
            evidence={"judgment": {"score": 0.9}},
        )

        card_state = interview_service.update_card_state(
            db=mock_db, session_id="session-123", card_state_id="state-123", update_data=update_data
        )

        assert card_state.status == "sufficient"
        assert card_state.confidence == 0.9
        assert card_state.answered_at is not None
        mock_db.commit.assert_called_once()

    def test_update_card_state_not_found(self, mock_db, sample_interview_session):
        """Test update card state fails when not found."""
        mock_db.query().filter().first.side_effect = [sample_interview_session, None]

        update_data = InterviewCardStateUpdate(status="sufficient", confidence=0.9)

        with pytest.raises(HTTPException) as exc_info:
            interview_service.update_card_state(
                db=mock_db,
                session_id="session-123",
                card_state_id="nonexistent",
                update_data=update_data,
            )

        assert exc_info.value.status_code == 404

    def test_get_all_card_states(self, mock_db, sample_interview_session):
        """Test getting all card states for a session."""
        card_states = [
            InterviewCardState(
                id="state-1", session_id="session-123", question_card_id="card-1", status="pending"
            ),
            InterviewCardState(
                id="state-2",
                session_id="session-123",
                question_card_id="card-2",
                status="sufficient",
            ),
        ]

        mock_db.query().filter().first.return_value = sample_interview_session
        mock_db.query().filter().all.return_value = card_states

        result = interview_service.get_all_card_states(mock_db, "session-123")

        assert len(result) == 2

    @patch("app.services.interview_service.uuid")
    def test_create_utterance_success(self, mock_uuid, mock_db, sample_interview_session):
        """Test creating an utterance."""
        mock_uuid.uuid4().hex = "utt123"
        mock_db.query().filter().first.return_value = sample_interview_session

        from app.schemas.interview import UtteranceCreate

        utterance_data = UtteranceCreate(
            sectionId="section-1",
            speaker="interviewee",
            transcript="This is my answer",
            startedAt=datetime.utcnow(),
            endedAt=datetime.utcnow(),
        )

        utterance = interview_service.create_utterance(
            db=mock_db, session_id="session-123", utterance_data=utterance_data
        )

        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_get_utterances_all(self, mock_db, sample_interview_session):
        """Test getting all utterances for a session."""
        utterances = [
            Utterance(
                id="utt-1", session_id="session-123", speaker="interviewer", transcript="Question?"
            ),
            Utterance(
                id="utt-2", session_id="session-123", speaker="interviewee", transcript="Answer"
            ),
        ]

        mock_db.query().filter().first.return_value = sample_interview_session
        mock_db.query().filter().order_by().limit().all.return_value = utterances

        result = interview_service.get_utterances(mock_db, "session-123")

        assert len(result) == 2

    def test_list_sessions(self, mock_db):
        """Test listing interview sessions for a user."""
        sessions = [
            (
                InterviewSession(
                    id="session-1",
                    document_id="doc-1",
                    prep_session_id="prep-1",
                    user_id="user-123",
                    status="ended",
                    started_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                ),
                "Document Title 1",
            )
        ]

        mock_db.query().join().filter().count.return_value = 1
        mock_db.query().join().filter().order_by().limit().offset().all.return_value = sessions

        with patch("app.services.interview_service.billing_service") as mock_billing:
            mock_billing.summarize_sessions.return_value = {"session-1": {"totalCostUsd": 0.5}}
            result = interview_service.list_sessions(
                db=mock_db, user_id="user-123", limit=50, offset=0
            )

        assert result.total == 1
        assert len(result.sessions) == 1

    def test_delete_session_success(self, mock_db, sample_interview_session):
        """Test deleting an interview session."""
        mock_db.query().filter().first.return_value = sample_interview_session
        mock_db.query().filter().delete.return_value = None

        interview_service.delete_session(mock_db, "session-123")

        # Should delete card states, utterances, and session
        mock_db.delete.assert_called_once_with(sample_interview_session)
        mock_db.commit.assert_called_once()

    def test_delete_session_not_found(self, mock_db):
        """Test delete session fails when not found."""
        mock_db.query().filter().first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            interview_service.delete_session(mock_db, "nonexistent")

        assert exc_info.value.status_code == 404
