"""
Unit tests for Answer Evaluation Engine
Tests core answer evaluation logic and sufficiency scoring.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.services.answer_evaluation_engine import answer_evaluation_engine
from app.models.question_card import QuestionCard
from app.models.interview_session import InterviewSession, InterviewCardState
from app.models.utterance import Utterance


class TestAnswerEvaluationEngine:
    """Test suite for answer evaluation engine."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        return db

    @pytest.fixture
    def sample_question_card(self):
        """Create a sample question card."""
        return QuestionCard(
            id="card-123",
            document_id="doc-456",
            section_id="section-789",
            question_text="What are the main business objectives?",
            question_type="objectives",
            expected_answer_elements=["Increase revenue", "Improve efficiency", "Expand market"],
            coverage_rule={
                "mustMentionElements": ["revenue target", "efficiency goal", "market expansion"],
                "semanticAnchors": []
            }
        )

    @pytest.fixture
    def sample_interview_session(self):
        """Create a sample interview session."""
        return InterviewSession(
            id="session-123",
            document_id="doc-456",
            user_id="user-789",
            status="interviewing",
            started_at=datetime.utcnow()
        )

    @pytest.fixture
    def sample_card_state(self):
        """Create a sample card state."""
        return InterviewCardState(
            id="state-123",
            session_id="session-123",
            question_card_id="card-123",
            status="listening",
            confidence=0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    def test_engine_initialization(self):
        """Test that the engine initializes correctly."""
        assert answer_evaluation_engine is not None
        assert hasattr(answer_evaluation_engine, 'process_utterance')
        assert hasattr(answer_evaluation_engine, 'embedding_service')
        assert hasattr(answer_evaluation_engine, 'scoring_service')
        assert hasattr(answer_evaluation_engine, 'semantic_judge')

    def test_get_required_element_ids_with_must_mention(self, sample_question_card):
        """Test extracting required element IDs from mustMentionElements."""
        element_ids = answer_evaluation_engine._get_required_element_ids(sample_question_card)

        assert isinstance(element_ids, list)
        assert len(element_ids) == 3
        assert "element_0" in element_ids
        assert "element_1" in element_ids
        assert "element_2" in element_ids

    def test_get_required_element_ids_with_semantic_anchors(self):
        """Test extracting required element IDs from semanticAnchors."""
        card = QuestionCard(
            id="card-1",
            document_id="doc-1",
            section_id="section-1",
            question_text="Test question",
            coverage_rule={
                "semanticAnchors": ["anchor1", "anchor2"],
                "mustMentionElements": []
            }
        )

        element_ids = answer_evaluation_engine._get_required_element_ids(card)

        assert len(element_ids) == 2
        assert "anchor_0" in element_ids
        assert "anchor_1" in element_ids

    def test_get_required_element_ids_empty(self):
        """Test with no coverage rules."""
        card = QuestionCard(
            id="card-1",
            document_id="doc-1",
            section_id="section-1",
            question_text="Test question",
            coverage_rule={}
        )

        element_ids = answer_evaluation_engine._get_required_element_ids(card)
        assert element_ids == []

    def test_canonicalize_element_ids(self, sample_question_card):
        """Test canonicalizing element IDs."""
        element_ids = {"element_0", "element_1", "anchor_0"}

        canonical = answer_evaluation_engine._canonicalize_element_ids(
            sample_question_card,
            element_ids
        )

        assert "element_0" in canonical
        assert "element_1" in canonical

    def test_calculate_element_progress_full_coverage(self, sample_question_card):
        """Test progress calculation with full coverage."""
        covered_ids = {"element_0", "element_1", "element_2"}

        progress = answer_evaluation_engine._calculate_element_progress(
            sample_question_card,
            covered_ids
        )

        assert progress == 1.0

    def test_calculate_element_progress_partial_coverage(self, sample_question_card):
        """Test progress calculation with partial coverage."""
        covered_ids = {"element_0", "element_1"}

        progress = answer_evaluation_engine._calculate_element_progress(
            sample_question_card,
            covered_ids
        )

        assert progress == pytest.approx(0.666, rel=0.01)

    def test_calculate_element_progress_no_coverage(self, sample_question_card):
        """Test progress calculation with no coverage."""
        covered_ids = set()

        progress = answer_evaluation_engine._calculate_element_progress(
            sample_question_card,
            covered_ids
        )

        assert progress == 0.0

    def test_calculate_element_progress_no_required_elements(self):
        """Test progress calculation when card has no required elements."""
        card = QuestionCard(
            id="card-1",
            document_id="doc-1",
            section_id="section-1",
            question_text="Test",
            coverage_rule={}
        )

        progress = answer_evaluation_engine._calculate_element_progress(card, set())
        assert progress is None

    def test_interviewer_card_match_prefers_current_chinese_question(self):
        """Test active-card matching for similar Chinese interview questions."""
        utterance = "請問你們可以稍微描述一下需求訪談助手這個 agent主要是想要達到什麼目標嗎？"
        first_card = QuestionCard(
            id="card-1",
            document_id="doc-1",
            section_id="section-1",
            question_text="能否描述需求訪談助手的agent的主要目標是什麼？",
            coverage_rule={}
        )
        second_card = QuestionCard(
            id="card-2",
            document_id="doc-1",
            section_id="section-1",
            question_text="需求訪談助手的agent主要針對哪些需求範圍進行支援？",
            coverage_rule={}
        )

        first_score = answer_evaluation_engine._score_interviewer_card_match(utterance, first_card)
        second_score = answer_evaluation_engine._score_interviewer_card_match(utterance, second_card)

        assert first_score > second_score

    def test_interviewer_card_match_treats_problem_to_solve_as_goal(self):
        """Test 'problem to solve' phrasing activates the goal card, not scope."""
        utterance = "請說明一下這個需求訪談助手在第一個階段想要解決的是什麼問題呢?"
        first_card = QuestionCard(
            id="card-1",
            document_id="doc-1",
            section_id="section-1",
            question_text="能否描述需求訪談助手的agent的主要目標是什麼？",
            coverage_rule={}
        )
        second_card = QuestionCard(
            id="card-2",
            document_id="doc-1",
            section_id="section-1",
            question_text="需求訪談助手的agent主要針對哪些需求範圍進行支援？",
            coverage_rule={}
        )

        first_score = answer_evaluation_engine._score_interviewer_card_match(utterance, first_card)
        second_score = answer_evaluation_engine._score_interviewer_card_match(utterance, second_card)

        assert first_score > second_score

    def test_interviewer_question_activates_without_progress(self, mock_db, sample_question_card):
        """Test interviewer questions mark a card active without increasing confidence."""
        card_state = InterviewCardState(
            id="state-123",
            session_id="session-123",
            question_card_id=sample_question_card.id,
            status="pending",
            confidence=0.0,
        )

        with patch.object(answer_evaluation_engine, '_load_candidate_cards') as mock_load:
            mock_load.return_value = [{'card': sample_question_card, 'state': card_state}]

            updates = answer_evaluation_engine._process_interviewer_question(
                db=mock_db,
                session_id="session-123",
                section_id="section-789",
                utterance_text="What are the main business objectives?",
            )

        assert len(updates) == 1
        assert card_state.status == "listening"
        assert float(card_state.confidence or 0) == 0
        assert updates[0]["new_status"] == "listening"
        assert updates[0]["confidence"] == 0
        assert updates[0]["evidence"]["activeOnly"] is True

    def test_interviewer_question_matching_completed_card_does_not_activate_other(self, mock_db):
        """Test asking an already completed question does not activate a weaker match."""
        completed_card = QuestionCard(
            id="card-1",
            document_id="doc-1",
            section_id="section-1",
            question_text="能否描述需求訪談助手的agent的主要目標是什麼？",
            coverage_rule={}
        )
        other_card = QuestionCard(
            id="card-2",
            document_id="doc-1",
            section_id="section-1",
            question_text="需求訪談助手的agent主要針對哪些需求範圍進行支援？",
            coverage_rule={}
        )
        completed_state = InterviewCardState(
            id="state-1",
            session_id="session-123",
            question_card_id="card-1",
            status="sufficient",
            confidence=1,
        )
        other_state = InterviewCardState(
            id="state-2",
            session_id="session-123",
            question_card_id="card-2",
            status="pending",
            confidence=0,
        )

        candidate_cards = [
            {'card': completed_card, 'state': completed_state},
            {'card': other_card, 'state': other_state},
        ]
        with (
            patch.object(answer_evaluation_engine, '_load_candidate_cards') as mock_load,
            patch.object(answer_evaluation_engine, '_semantic_interviewer_card_match') as mock_semantic,
        ):
            mock_load.return_value = candidate_cards
            mock_semantic.return_value = candidate_cards[0]

            updates = answer_evaluation_engine._process_interviewer_question(
                db=mock_db,
                session_id="session-123",
                section_id="section-789",
                utterance_text="可以稍微描述一下需求訪談助手 agent 的主要目標是什麼呢？",
            )

        assert updates == []
        assert other_state.status == "pending"

    def test_interviewer_question_uses_ai_semantic_match(self, mock_db):
        """Test AI semantic matching can activate the intended unfinished card."""
        completed_card = QuestionCard(
            id="card-1",
            document_id="doc-1",
            section_id="section-1",
            question_text="能否描述需求訪談助手的agent的主要目標是什麼？",
            coverage_rule={}
        )
        scope_card = QuestionCard(
            id="card-2",
            document_id="doc-1",
            section_id="section-1",
            question_text="需求訪談助手的agent主要針對哪些需求範圍進行支援？",
            coverage_rule={}
        )
        completed_state = InterviewCardState(
            id="state-1",
            session_id="session-123",
            question_card_id="card-1",
            status="sufficient",
            confidence=1,
        )
        scope_state = InterviewCardState(
            id="state-2",
            session_id="session-123",
            question_card_id="card-2",
            status="pending",
            confidence=0,
        )
        candidate_cards = [
            {'card': completed_card, 'state': completed_state},
            {'card': scope_card, 'state': scope_state},
        ]

        with (
            patch.object(answer_evaluation_engine, '_load_candidate_cards') as mock_load,
            patch.object(answer_evaluation_engine, '_semantic_interviewer_card_match') as mock_semantic,
        ):
            mock_load.return_value = candidate_cards
            mock_semantic.return_value = candidate_cards[1]

            updates = answer_evaluation_engine._process_interviewer_question(
                db=mock_db,
                session_id="session-123",
                section_id="section-789",
                utterance_text="那這個助手第一階段主要支援哪些需求訪談情境？",
            )

        assert len(updates) == 1
        assert updates[0]["card_id"] == "card-2"
        assert scope_state.status == "listening"

    def test_interviewer_question_prefers_unfinished_tied_match(self, mock_db):
        """Test deterministic fallback can activate the unfinished scope card."""
        completed_card = QuestionCard(
            id="card-1",
            document_id="doc-1",
            section_id="section-1",
            question_text="能否描述需求訪談助手的agent的主要目標是什麼？",
            coverage_rule={}
        )
        scope_card = QuestionCard(
            id="card-2",
            document_id="doc-1",
            section_id="section-1",
            question_text="需求訪談助手的agent主要針對哪些需求範圍進行支援？",
            coverage_rule={}
        )
        completed_state = InterviewCardState(
            id="state-1",
            session_id="session-123",
            question_card_id="card-1",
            status="sufficient",
            confidence=1,
        )
        scope_state = InterviewCardState(
            id="state-2",
            session_id="session-123",
            question_card_id="card-2",
            status="pending",
            confidence=0,
        )

        with (
            patch.object(answer_evaluation_engine, '_load_candidate_cards') as mock_load,
            patch.object(answer_evaluation_engine, '_semantic_interviewer_card_match') as mock_semantic,
        ):
            mock_load.return_value = [
                {'card': completed_card, 'state': completed_state},
                {'card': scope_card, 'state': scope_state},
            ]
            mock_semantic.return_value = None

            updates = answer_evaluation_engine._process_interviewer_question(
                db=mock_db,
                session_id="session-123",
                section_id="section-789",
                utterance_text="那這個助手在第一階段需要支援哪些需求訪談的情境呢？",
            )

        assert len(updates) == 1
        assert updates[0]["card_id"] == "card-2"
        assert scope_state.status == "listening"

    def test_interviewer_question_completed_match_fallback_does_not_activate_weaker(self, mock_db):
        """Test deterministic fallback still protects completed-card re-asks."""
        completed_card = QuestionCard(
            id="card-1",
            document_id="doc-1",
            section_id="section-1",
            question_text="能否描述需求訪談助手的agent的主要目標是什麼？",
            coverage_rule={}
        )
        other_card = QuestionCard(
            id="card-2",
            document_id="doc-1",
            section_id="section-1",
            question_text="需求訪談助手的agent主要針對哪些需求範圍進行支援？",
            coverage_rule={}
        )
        completed_state = InterviewCardState(
            id="state-1",
            session_id="session-123",
            question_card_id="card-1",
            status="sufficient",
            confidence=1,
        )
        other_state = InterviewCardState(
            id="state-2",
            session_id="session-123",
            question_card_id="card-2",
            status="pending",
            confidence=0,
        )

        with (
            patch.object(answer_evaluation_engine, '_load_candidate_cards') as mock_load,
            patch.object(answer_evaluation_engine, '_semantic_interviewer_card_match') as mock_semantic,
        ):
            mock_load.return_value = [
                {'card': completed_card, 'state': completed_state},
                {'card': other_card, 'state': other_state},
            ]
            mock_semantic.return_value = None

            updates = answer_evaluation_engine._process_interviewer_question(
                db=mock_db,
                session_id="session-123",
                section_id="section-789",
                utterance_text="可以稍微描述一下需求訪談助手 agent 的主要目標是什麼呢？",
            )

        assert updates == []
        assert other_state.status == "pending"

    def test_normalize_completion_element_ids_sufficient(self, sample_question_card):
        """Test normalization when answer is sufficient."""
        completion = {
            "covered_element_ids": ["element_0", "element_1"],
            "missing_element_ids": ["element_2"]
        }

        covered, missing = answer_evaluation_engine._normalize_completion_element_ids(
            sample_question_card,
            completion,
            completion_percentage=90.0,
            is_sufficient=True
        )

        # When sufficient and high completion, all elements should be covered
        assert len(covered) == 3
        assert len(missing) == 0

    def test_normalize_completion_element_ids_insufficient(self, sample_question_card):
        """Test normalization when answer is insufficient."""
        completion = {
            "covered_element_ids": ["element_0"],
            "missing_element_ids": ["element_1", "element_2"]
        }

        covered, missing = answer_evaluation_engine._normalize_completion_element_ids(
            sample_question_card,
            completion,
            completion_percentage=33.0,
            is_sufficient=False
        )

        assert len(covered) == 1
        assert len(missing) == 2
        assert "element_0" in covered

    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._load_candidate_cards')
    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._get_answer_context_for_cards')
    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._batch_judge_answer_sufficiency')
    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._update_card_state')
    def test_process_utterance_interviewee(
        self,
        mock_update,
        mock_batch_judge,
        mock_context,
        mock_load,
        mock_db,
        sample_question_card,
        sample_card_state
    ):
        """Test processing an interviewee utterance."""
        # Setup mocks
        mock_load.return_value = [{'card': sample_question_card, 'state': sample_card_state}]
        mock_context.return_value = "We need to increase revenue by 20%"
        mock_batch_judge.return_value = [{
            'sufficiency_score': 0.8,
            'is_sufficient': True,
            'completion_percentage': 85
        }]
        mock_update.return_value = {
            'card_id': 'card-123',
            'new_status': 'sufficient'
        }

        # Execute
        updates = answer_evaluation_engine.process_utterance(
            db=mock_db,
            session_id="session-123",
            utterance_id="utt-123",
            utterance_text="We need to increase revenue by 20%",
            section_id="section-789",
            speaker="interviewee"
        )

        # Verify
        assert len(updates) == 1
        assert updates[0]['card_id'] == 'card-123'
        mock_load.assert_called_once_with(
            mock_db,
            "session-123",
            "section-789",
            statuses=['listening'],
        )
        mock_batch_judge.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._load_candidate_cards')
    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._get_answer_context_for_cards')
    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._batch_judge_answer_sufficiency')
    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._update_card_state')
    def test_process_utterance_uses_active_card_before_section_fallback(
        self,
        mock_update,
        mock_batch_judge,
        mock_context,
        mock_load,
        mock_db,
        sample_question_card,
        sample_card_state
    ):
        """Test completed utterances only evaluate the active listening card when present."""
        mock_load.side_effect = [
            [{'card': sample_question_card, 'state': sample_card_state}],
            AssertionError("section fallback should not run when active card exists"),
        ]
        mock_context.return_value = "Active answer"
        mock_batch_judge.return_value = [{'confidence': 0.7, 'is_covered': True}]
        mock_update.return_value = {'card_id': 'card-123', 'new_status': 'sufficient'}

        updates = answer_evaluation_engine.process_utterance(
            db=mock_db,
            session_id="session-123",
            utterance_id="utt-123",
            utterance_text="Active answer",
            section_id="section-789",
            speaker="interviewee"
        )

        assert len(updates) == 1
        assert mock_load.call_count == 1
        mock_load.assert_called_once_with(
            mock_db,
            "session-123",
            "section-789",
            statuses=['listening'],
        )

    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._load_candidate_cards')
    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._get_answer_context_for_cards')
    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._batch_judge_answer_sufficiency')
    def test_process_utterance_skips_when_no_active_card(
        self,
        mock_batch_judge,
        mock_context,
        mock_load,
        mock_db,
    ):
        """Test completed utterances do not fallback to pending cards."""
        mock_load.return_value = []

        updates = answer_evaluation_engine.process_utterance(
            db=mock_db,
            session_id="session-123",
            utterance_id="utt-123",
            utterance_text="This is an answer after the active card was completed by partial matching.",
            section_id="section-789",
            speaker="interviewee"
        )

        assert updates == []
        mock_load.assert_called_once_with(
            mock_db,
            "session-123",
            "section-789",
            statuses=['listening'],
        )
        mock_context.assert_not_called()
        mock_batch_judge.assert_not_called()

    def test_process_utterance_interviewer_skipped(self, mock_db):
        """Test that interviewer utterances are skipped."""
        updates = answer_evaluation_engine.process_utterance(
            db=mock_db,
            session_id="session-123",
            utterance_id="utt-123",
            utterance_text="Can you tell me about the objectives?",
            section_id="section-789",
            speaker="interviewer"
        )

        assert len(updates) == 0
        mock_db.commit.assert_not_called()

    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._load_candidate_cards')
    def test_process_utterance_no_candidates(self, mock_load, mock_db):
        """Test processing when no candidate cards exist."""
        mock_load.return_value = []

        updates = answer_evaluation_engine.process_utterance(
            db=mock_db,
            session_id="session-123",
            utterance_id="utt-123",
            utterance_text="Test utterance",
            section_id="section-789",
            speaker="interviewee"
        )

        assert len(updates) == 0

    @patch('app.services.answer_evaluation_engine.answer_evaluation_engine._load_candidate_cards')
    def test_process_utterance_error_handling(self, mock_load, mock_db):
        """Test error handling during utterance processing."""
        mock_load.side_effect = Exception("Database error")

        updates = answer_evaluation_engine.process_utterance(
            db=mock_db,
            session_id="session-123",
            utterance_id="utt-123",
            utterance_text="Test utterance",
            section_id="section-789",
            speaker="interviewee"
        )

        assert len(updates) == 0
        mock_db.rollback.assert_called_once()

    def test_load_candidate_cards(self, mock_db, sample_interview_session, sample_question_card):
        """Test loading candidate cards for evaluation."""
        card_state = InterviewCardState(
            id="state-1",
            session_id=sample_interview_session.id,
            question_card_id=sample_question_card.id,
            status="listening"
        )

        # Build a mock that responds differently based on query sequence
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        # first() returns session, all() returns cards/states alternating
        mock_query.first.return_value = sample_interview_session
        mock_query.all.side_effect = [
            [sample_question_card],  # QuestionCard query
            [card_state]             # InterviewCardState query
        ]
        mock_db.query.return_value = mock_query

        # Execute
        candidates = answer_evaluation_engine._load_candidate_cards(
            mock_db,
            sample_interview_session.id,
            "section-789"
        )

        # Verify
        assert len(candidates) == 1
        assert candidates[0]['card'] == sample_question_card
        assert candidates[0]['state'] == card_state

    def test_load_candidate_cards_session_not_found(self, mock_db):
        """Test loading candidates when session doesn't exist."""
        mock_db.query().filter().first.return_value = None

        candidates = answer_evaluation_engine._load_candidate_cards(
            mock_db,
            "nonexistent-session",
            "section-789"
        )

        assert candidates == []

    def test_get_recent_context(self, mock_db):
        """Test building recent context from utterances."""
        utterances = [
            Utterance(
                id="utt-1",
                session_id="session-123",
                section_id="section-789",
                speaker="interviewee",
                transcript="First utterance",
                created_at=datetime.utcnow()
            ),
            Utterance(
                id="utt-2",
                session_id="session-123",
                section_id="section-789",
                speaker="interviewee",
                transcript="Second utterance",
                created_at=datetime.utcnow()
            )
        ]

        # Build the mock chain properly so .all() returns a real list
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = utterances
        mock_db.query.return_value = mock_query

        context = answer_evaluation_engine._get_recent_context(
            mock_db,
            "session-123",
            "section-789",
            "Current utterance"
        )

        assert "Current utterance" in context
        assert isinstance(context, str)

    def test_get_answer_context_without_active_boundary_uses_current_only(self, mock_db):
        """Test missing activeAt does not pull old section answers into judgment."""
        card_state = InterviewCardState(
            id="state-1",
            session_id="session-123",
            question_card_id="card-1",
            status="listening",
            confidence=0,
            evidence={},
        )

        context = answer_evaluation_engine._get_answer_context_for_cards(
            db=mock_db,
            session_id="session-123",
            section_id="section-789",
            current_text="Current answer",
            candidate_cards=[{"card": Mock(id="card-1"), "state": card_state}],
        )

        assert context == "Current answer"
        mock_db.query.assert_not_called()

    def test_get_recent_context_since_applies_active_question_boundary(self, mock_db):
        """Test bounded context query filters out utterances before activeAt."""
        active_since = datetime.utcnow() - timedelta(seconds=30)
        utterances = [
            Utterance(
                id="utt-new",
                session_id="session-123",
                section_id="section-789",
                speaker="interviewee",
                transcript="Answer after active question",
                created_at=active_since + timedelta(seconds=3),
            )
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = utterances
        mock_db.query.return_value = mock_query

        context = answer_evaluation_engine._get_recent_context_since(
            db=mock_db,
            session_id="session-123",
            section_id="section-789",
            current_text="Current answer",
            since=active_since,
        )

        filter_args = mock_query.filter.call_args.args
        assert len(filter_args) == 4
        assert "Answer after active question" in context
        assert "Current answer" in context

    def test_judge_answer_sufficiency(self, sample_question_card):
        """Test AI sufficiency judgment."""
        mock_judge = Mock()
        mock_judge.judge_coverage.return_value = {
            'is_covered': True,
            'confidence': 0.9,
            'reasoning': 'Complete answer',
            'mentioned_keywords': ['revenue', 'growth'],
            'missing_aspects': []
        }

        # Patch the instance attribute directly
        original_judge = answer_evaluation_engine.semantic_judge
        answer_evaluation_engine.semantic_judge = mock_judge

        try:
            judgment = answer_evaluation_engine._judge_answer_sufficiency(
                context="We want to increase revenue by 25% this year",
                card=sample_question_card,
                session_id="session-123"
            )

            assert judgment['confidence'] == 0.9
            assert judgment['is_covered'] is True
            mock_judge.judge_coverage.assert_called_once()
        finally:
            answer_evaluation_engine.semantic_judge = original_judge

    def test_update_card_state_to_sufficient(self, mock_db, sample_card_state, sample_question_card):
        """Test updating card state to sufficient."""
        judgment = {
            'sufficiency_score': 0.9,
            'is_sufficient': True,
            'completion_percentage': 90
        }

        update = answer_evaluation_engine._update_card_state(
            db=mock_db,
            card_state=sample_card_state,
            card=sample_question_card,
            utterance_id="utt-123",
            utterance_text="Complete answer with all elements",
            judgment=judgment
        )

        assert update is not None
        assert update['new_status'] == 'sufficient'
        assert sample_card_state.status == 'sufficient'
        assert sample_card_state.confidence == 0.9
        assert sample_card_state.answered_at is not None

    def test_update_card_state_to_probably_sufficient(self, mock_db, sample_card_state, sample_question_card):
        """Test updating card state to probably_sufficient."""
        judgment = {
            'sufficiency_score': 0.7,
            'is_sufficient': False,
            'completion_percentage': 70
        }

        update = answer_evaluation_engine._update_card_state(
            db=mock_db,
            card_state=sample_card_state,
            card=sample_question_card,
            utterance_id="utt-123",
            utterance_text="Partial answer",
            judgment=judgment
        )

        assert update is not None
        assert update['new_status'] == 'probably_sufficient'
        assert sample_card_state.status == 'probably_sufficient'

    def test_update_card_state_no_change(self, mock_db, sample_card_state, sample_question_card):
        """Test that no update is returned when status doesn't change."""
        sample_card_state.status = "listening"

        judgment = {
            'sufficiency_score': 0.3,
            'is_sufficient': False,
            'completion_percentage': 30
        }

        update = answer_evaluation_engine._update_card_state(
            db=mock_db,
            card_state=sample_card_state,
            card=sample_question_card,
            utterance_id="utt-123",
            utterance_text="Weak answer",
            judgment=judgment
        )

        # Should transition from pending to listening, so update should exist
        # But if already listening, no change
        assert sample_card_state.status == "listening"

    def test_update_card_state_from_pending_to_listening(self, mock_db, sample_question_card):
        """Test transition from pending to listening."""
        card_state = InterviewCardState(
            id="state-123",
            session_id="session-123",
            question_card_id="card-123",
            status="pending",
            confidence=0.0
        )

        judgment = {
            'sufficiency_score': 0.4,
            'is_sufficient': False,
            'completion_percentage': 40
        }

        update = answer_evaluation_engine._update_card_state(
            db=mock_db,
            card_state=card_state,
            card=sample_question_card,
            utterance_id="utt-123",
            utterance_text="Starting to answer",
            judgment=judgment
        )

        assert update is not None
        assert update['old_status'] == 'pending'
        assert update['new_status'] == 'listening'
        assert card_state.status == 'listening'

    def test_process_partial_transcript(self, mock_db):
        """Test processing partial transcript (streaming)."""
        candidate = {'card': Mock(id='card-123'), 'state': Mock(id='state-123')}
        with (
            patch.object(answer_evaluation_engine, '_load_candidate_cards') as mock_load,
            patch.object(answer_evaluation_engine, '_batch_judge_answer_sufficiency') as mock_judge,
            patch.object(answer_evaluation_engine, '_update_card_state') as mock_update,
        ):
            mock_load.return_value = [candidate]
            mock_judge.return_value = [{'confidence': 0.5, 'is_covered': False}]
            mock_update.return_value = {'card_id': 'card-123', 'new_status': 'listening'}

            updates = answer_evaluation_engine.process_partial_transcript(
                db=mock_db,
                session_id="session-123",
                transcript_text="This is a partial transcript from streaming",
                section_id="section-789",
                speaker="interviewee",
                active_card_id="card-123",
            )

            assert len(updates) == 1
            mock_load.assert_called_once_with(
                mock_db,
                "session-123",
                "section-789",
                active_card_id="card-123",
                statuses=['listening'],
            )
            mock_judge.assert_called_once()
            mock_update.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_process_partial_transcript_too_short(self, mock_db):
        """Test that very short partial transcripts are ignored."""
        updates = answer_evaluation_engine.process_partial_transcript(
            db=mock_db,
            session_id="session-123",
            transcript_text="short",
            section_id="section-789",
            speaker="interviewee"
        )

        assert len(updates) == 0

    def test_process_partial_transcript_interviewer_ignored(self, mock_db):
        """Test that partial transcripts from interviewer are ignored."""
        updates = answer_evaluation_engine.process_partial_transcript(
            db=mock_db,
            session_id="session-123",
            transcript_text="Can you elaborate on that?",
            section_id="section-789",
            speaker="interviewer"
        )

        assert len(updates) == 0

    def test_process_partial_transcript_error_handling(self, mock_db):
        """Test error handling in partial transcript processing."""
        with patch.object(answer_evaluation_engine, '_load_candidate_cards') as mock_load:
            mock_load.side_effect = Exception("Processing error")

            updates = answer_evaluation_engine.process_partial_transcript(
                db=mock_db,
                session_id="session-123",
                transcript_text="This will cause an error",
                section_id="section-789",
                speaker="interviewee"
            )

            assert len(updates) == 0
