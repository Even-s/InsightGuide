"""
Unit tests for Answer Evaluation Engine
Tests core answer evaluation logic and sufficiency scoring.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.models.interview_session import InterviewCardState, InterviewSession
from app.models.question_card import QuestionCard
from app.services.answer_evaluation_engine import answer_evaluation_engine
from app.services.evaluation import is_question_like, reduce_card_state


class TestAnswerEvaluationEngine:
    """Test suite for answer evaluation engine."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        # _get_next_evaluation_seq queries for max evaluation_seq — return None (first eval)
        db.query.return_value.filter.return_value.with_entities.return_value.order_by.return_value.first.return_value = (
            None
        )
        db.add = Mock()
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
                "semanticAnchors": [],
            },
        )

    @pytest.fixture
    def sample_interview_session(self):
        """Create a sample interview session."""
        return InterviewSession(
            id="session-123",
            document_id="doc-456",
            user_id="user-789",
            status="interviewing",
            started_at=datetime.utcnow(),
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
            activation_score=0.0,
            completion_score=0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

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
            coverage_rule={"semanticAnchors": ["anchor1", "anchor2"], "mustMentionElements": []},
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
            coverage_rule={},
        )

        element_ids = answer_evaluation_engine._get_required_element_ids(card)
        assert element_ids == []

    def test_canonicalize_element_ids(self, sample_question_card):
        """Test canonicalizing element IDs."""
        element_ids = {"element_0", "element_1", "anchor_0"}

        canonical = answer_evaluation_engine._canonicalize_element_ids(
            sample_question_card, element_ids
        )

        assert "element_0" in canonical
        assert "element_1" in canonical

    def test_normalize_completion_element_ids_sufficient(self, sample_question_card):
        """Test normalization does NOT auto-fill — only explicit coverage counts."""
        completion = {
            "covered_element_ids": ["element_0", "element_1"],
            "missing_element_ids": ["element_2"],
        }

        covered, missing = answer_evaluation_engine._normalize_completion_element_ids(
            sample_question_card, completion, completion_percentage=90.0, is_sufficient=True
        )

        # Only explicitly covered elements count — no auto-fill
        assert len(covered) == 2
        assert "element_0" in covered
        assert "element_1" in covered
        assert len(missing) == 1
        assert "element_2" in missing

    def test_normalize_completion_element_ids_insufficient(self, sample_question_card):
        """Test normalization when answer is insufficient."""
        completion = {
            "covered_element_ids": ["element_0"],
            "missing_element_ids": ["element_1", "element_2"],
        }

        covered, missing = answer_evaluation_engine._normalize_completion_element_ids(
            sample_question_card, completion, completion_percentage=33.0, is_sufficient=False
        )

        assert len(covered) == 1
        assert len(missing) == 2
        assert "element_0" in covered

    def test_process_utterance_interviewer_skipped(self, mock_db):
        """Test that interviewer utterances are skipped."""
        updates = answer_evaluation_engine.process_utterance(
            db=mock_db,
            session_id="session-123",
            utterance_id="utt-123",
            utterance_text="Can you tell me about the objectives?",
            section_id="section-789",
            speaker="interviewer",
        )

        assert len(updates) == 0
        mock_db.commit.assert_not_called()

    @patch("app.services.answer_evaluation_engine.answer_evaluation_engine._load_candidate_cards")
    def test_process_utterance_no_candidates(self, mock_load, mock_db):
        """Test processing when no candidate cards exist."""
        mock_load.return_value = []

        updates = answer_evaluation_engine.process_utterance(
            db=mock_db,
            session_id="session-123",
            utterance_id="utt-123",
            utterance_text="Test utterance",
            section_id="section-789",
            speaker="interviewee",
        )

        assert len(updates) == 0

    @patch("app.services.answer_evaluation_engine.answer_evaluation_engine._load_candidate_cards")
    def test_process_utterance_error_handling(self, mock_load, mock_db):
        """Test error handling during utterance processing."""
        mock_load.side_effect = Exception("Database error")

        updates = answer_evaluation_engine.process_utterance(
            db=mock_db,
            session_id="session-123",
            utterance_id="utt-123",
            utterance_text="Test utterance",
            section_id="section-789",
            speaker="interviewee",
        )

        assert len(updates) == 0
        mock_db.rollback.assert_called_once()

    def test_load_candidate_cards(self, mock_db, sample_interview_session, sample_question_card):
        """Test loading candidate cards for evaluation."""
        card_state = InterviewCardState(
            id="state-1",
            session_id=sample_interview_session.id,
            question_card_id=sample_question_card.id,
            status="listening",
        )

        # Build a mock that responds differently based on query sequence
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        # first() returns session, all() returns cards/states alternating
        mock_query.first.return_value = sample_interview_session
        mock_query.all.side_effect = [
            [sample_question_card],  # QuestionCard query
            [card_state],  # InterviewCardState query
        ]
        mock_db.query.return_value = mock_query

        # Execute
        candidates = answer_evaluation_engine._load_candidate_cards(
            mock_db, sample_interview_session.id, "section-789"
        )

        # Verify
        assert len(candidates) == 1
        assert candidates[0]["card"] == sample_question_card
        assert candidates[0]["state"] == card_state

    def test_load_candidate_cards_session_not_found(self, mock_db):
        """Test loading candidates when session doesn't exist."""
        mock_db.query().filter().first.return_value = None

        candidates = answer_evaluation_engine._load_candidate_cards(
            mock_db, "nonexistent-session", "section-789"
        )

        assert candidates == []

    def test_update_card_state_keeps_existing_followup_when_next_is_empty(
        self,
        mock_db,
        sample_card_state,
        sample_question_card,
    ):
        """Test that a later complete judgment does not clear the follow-up prompt."""
        sample_card_state.evidence = {
            "judgment": {
                "suggested_followup": "Can you clarify the timeline?",
                "reason": "Timeline is missing.",
            }
        }

        judgment = {
            "sufficiency_score": 0.7,
            "is_sufficient": False,
            "completion_percentage": 70,
            "reason": "Scope is clearer now.",
            "suggested_followup": "",
            "response_status": "responded",
        }

        update = answer_evaluation_engine._update_card_state(
            db=mock_db,
            card_state=sample_card_state,
            card=sample_question_card,
            utterance_id="utt-123",
            utterance_text="Partial answer with more scope detail",
            judgment=judgment,
        )

        assert update is not None
        assert (
            update["evidence"]["judgment"]["suggested_followup"] == "Can you clarify the timeline?"
        )
        assert (
            sample_card_state.evidence["judgment"]["suggested_followup"]
            == "Can you clarify the timeline?"
        )
        assert sample_card_state.evidence["judgment"]["reason"] == "Scope is clearer now."

    def test_update_card_state_no_change(self, mock_db, sample_card_state, sample_question_card):
        """Test that no update is returned when status doesn't change."""
        sample_card_state.status = "listening"

        judgment = {"sufficiency_score": 0.3, "is_sufficient": False, "completion_percentage": 30}

        update = answer_evaluation_engine._update_card_state(
            db=mock_db,
            card_state=sample_card_state,
            card=sample_question_card,
            utterance_id="utt-123",
            utterance_text="Weak answer",
            judgment=judgment,
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
            confidence=0.0,
            activation_score=0.0,
            completion_score=0.0,
        )

        judgment = {
            "confidence": 0.1,
            "is_covered": False,
            "evidence_quote": "",
            "covered_element_ids": [],
            "missing_element_ids": ["criterion_0"],
        }

        update = answer_evaluation_engine._update_card_state(
            db=mock_db,
            card_state=card_state,
            card=sample_question_card,
            utterance_id="utt-123",
            utterance_text="Starting to answer",
            judgment=judgment,
        )

        assert update is not None
        assert update["old_status"] == "pending"
        assert update["new_status"] == "listening"
        assert card_state.status == "listening"

    def test_process_partial_transcript(self, mock_db):
        """Test processing partial transcript (streaming)."""
        candidate = {"card": Mock(id="card-123"), "state": Mock(id="state-123")}
        with (
            patch.object(answer_evaluation_engine, "_load_candidate_cards") as mock_load,
            patch.object(answer_evaluation_engine, "_batch_judge_answer_sufficiency") as mock_judge,
            patch.object(answer_evaluation_engine, "_update_card_state") as mock_update,
        ):
            mock_load.return_value = [candidate]
            mock_judge.return_value = [{"confidence": 0.5, "is_covered": False}]
            mock_update.return_value = {"card_id": "card-123", "new_status": "listening"}

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
                statuses=["listening"],
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
            speaker="interviewee",
        )

        assert len(updates) == 0

    def test_process_partial_transcript_interviewer_ignored(self, mock_db):
        """Test that partial transcripts from interviewer are ignored."""
        updates = answer_evaluation_engine.process_partial_transcript(
            db=mock_db,
            session_id="session-123",
            transcript_text="Can you elaborate on that?",
            section_id="section-789",
            speaker="interviewer",
        )

        assert len(updates) == 0

    def test_process_partial_transcript_error_handling(self, mock_db):
        """Test error handling in partial transcript processing."""
        with patch.object(answer_evaluation_engine, "_load_candidate_cards") as mock_load:
            mock_load.side_effect = Exception("Processing error")

            updates = answer_evaluation_engine.process_partial_transcript(
                db=mock_db,
                session_id="session-123",
                transcript_text="This will cause an error",
                section_id="section-789",
                speaker="interviewee",
            )

            assert len(updates) == 0


class TestQuestionGuardAndReduceState:
    """Tests for question-like utterance detection and state reduction with response_status."""

    def test_is_question_like_chinese_question_mark(self):
        assert is_question_like("你有哪些情境是需要馬上有人幫忙的呢？") is True

    def test_is_question_like_english_question_mark(self):
        assert is_question_like("What scenarios need help?") is True

    def test_is_question_like_ne_ending(self):
        assert is_question_like("你覺得哪裡最需要改進呢") is True

    def test_is_question_like_ma_ending(self):
        assert is_question_like("你有遇過這種情況嗎") is True

    def test_is_question_like_contains_marker(self):
        assert is_question_like("請問什麼時候會發生這個問題") is True

    def test_is_question_like_answer_not_detected(self):
        assert is_question_like("我們主要用 PostgreSQL 處理這個流程") is False

    def test_is_question_like_partial_answer_not_detected(self):
        assert is_question_like("最常遇到的情境是客戶突然改需求") is False

    def test_reduce_state_question_only_caps_at_listening(self):
        """question_only response_status must not produce probably_sufficient."""
        judgment = {
            "confidence": 0.5,
            "is_covered": False,
            "evidence_quote": "",
            "missing_element_ids": ["criterion_0"],
            "covered_element_ids": [],
            "response_status": "question_only",
        }
        state, _act, _comp = reduce_card_state("pending", judgment)
        assert state == "listening"
        assert _comp == 0.0

    def test_reduce_state_not_yet_caps_at_listening(self):
        """not_yet response_status must not produce probably_sufficient."""
        judgment = {
            "confidence": 0.5,
            "is_covered": False,
            "evidence_quote": "",
            "missing_element_ids": [],
            "covered_element_ids": [],
            "response_status": "not_yet",
        }
        state, _act, _comp = reduce_card_state("pending", judgment)
        assert state == "listening"

    def test_reduce_state_responded_allows_probably_sufficient(self):
        """responded status should allow probably_sufficient progression."""
        judgment = {
            "confidence": 0.5,
            "is_covered": False,
            "evidence_quote": "some evidence",
            "missing_element_ids": ["criterion_0"],
            "covered_element_ids": [],
            "response_status": "responded",
        }
        state, _act, _comp = reduce_card_state("pending", judgment)
        assert state == "probably_sufficient"

    def test_reduce_state_question_only_does_not_create_50_percent_progress(self):
        """A question-only turn must not create 50% completion."""
        judgment = {
            "confidence": 0.5,
            "is_covered": False,
            "evidence_quote": "你有哪些情境是需要馬上有人幫忙的呢？",
            "missing_element_ids": [],
            "covered_element_ids": ["criterion_0"],
            "response_status": "question_only",
        }
        state, _act, _comp = reduce_card_state("pending", judgment)
        assert state == "listening"
        assert _comp == 0.0

    def test_mislabeled_interviewer_question_does_not_advance(self):
        """A mislabeled interviewer question must not move a card to probably_sufficient.

        Simulates: speaker=interviewee but text is actually a question.
        The _is_question_like guard + _reduce_state response_status gate must prevent this.
        """
        text = "你有哪些情境是需要馬上有人幫忙的呢？"
        assert is_question_like(text) is True

        # Simulate what GPT might return (incorrectly)
        judgment_from_gpt = {
            "confidence": 0.5,
            "is_covered": False,
            "evidence_quote": "需要馬上有人幫忙",
            "missing_element_ids": [],
            "covered_element_ids": ["criterion_0"],
            "response_status": "responded",  # GPT incorrectly says responded
            "criterion_evaluations": [
                {
                    "criterion_id": "criterion_0",
                    "status": "partially_satisfied",
                    "evidence_quotes": ["需要馬上有人幫忙"],
                }
            ],
        }

        # After question guard in process_utterance, response_status should be overridden
        # because no criterion has status=satisfied and text is question-like
        has_satisfied = any(
            ce.get("status") == "satisfied"
            for ce in judgment_from_gpt.get("criterion_evaluations", [])
        )
        if not has_satisfied:
            judgment_from_gpt["response_status"] = "question_only"

        state, _act, _comp = reduce_card_state("pending", judgment_from_gpt)
        assert state == "listening"
        assert _comp == 0.0

    def test_real_partial_answer_still_advances(self):
        """A real partial answer should still move the card to probably_sufficient."""
        text = "最常遇到的情境是客戶突然改需求，我們來不及準備"
        assert is_question_like(text) is False

        judgment = {
            "confidence": 0.5,
            "is_covered": False,
            "evidence_quote": "客戶突然改需求",
            "missing_element_ids": [],
            "covered_element_ids": ["criterion_0"],
            "response_status": "responded",
        }
        state, _act, _comp = reduce_card_state("pending", judgment)
        assert state == "probably_sufficient"


class TestActivationCompletionSeparation:
    """Tests verifying clean separation between topic activation and answer completion."""

    def test_question_with_card_keywords_activates_but_no_completion(self):
        """A question mentioning card keywords should activate the card (listening)
        but keep completion_score = 0."""
        text = "哈嘍你好，就是目前你在銷售簡報的過程當中啊,最常需要有人幫忙的環節是什麼情境呢？"
        assert is_question_like(text) is True

        judgment = {
            "confidence": 0.5,
            "is_covered": False,
            "evidence_quote": "最常需要有人幫忙",
            "missing_element_ids": [],
            "covered_element_ids": ["criterion_0"],
            "response_status": "question_only",
            "relation": "topic_mention",
        }
        state, act, comp = reduce_card_state("pending", judgment)
        assert state == "listening"
        assert act == 1.0
        assert comp == 0.0

    def test_question_only_never_creates_partially_satisfied_evidence(self):
        """Question-only turns must not produce durable partially_satisfied evidence."""
        judgment = {
            "confidence": 0.5,
            "is_covered": False,
            "evidence_quote": "需要馬上有人幫忙",
            "response_status": "question_only",
            "relation": "topic_mention",
            "criterion_evaluations": [
                {
                    "criterion_id": "criterion_0",
                    "status": "partially_satisfied",
                    "evidence_quotes": ["需要馬上有人幫忙"],
                }
            ],
        }
        # Question-only statuses are handled by reduce_card_state to produce zero completion
        state, _act, comp = reduce_card_state("pending", judgment)
        assert comp == 0.0  # question_only must produce zero completion
        assert state in ("pending", "listening")  # can only activate, not complete

    def test_question_only_does_not_move_to_probably_sufficient(self):
        """A question-only turn must never move a card to probably_sufficient,
        regardless of the completion_score GPT returns."""
        # GPT incorrectly returns high confidence for a question
        judgment = {
            "confidence": 0.8,
            "is_covered": False,
            "evidence_quote": "有哪些情境",
            "missing_element_ids": [],
            "covered_element_ids": ["criterion_0"],
            "response_status": "question_only",
            "relation": "topic_mention",
        }
        state, act, comp = reduce_card_state("pending", judgment)
        assert state == "listening"
        assert comp == 0.0
        assert act == 1.0

    def test_real_partial_answer_creates_completion_progress(self):
        """A real answer should create non-zero completion_score and progress."""
        text = "像是客戶現場要我馬上確認折扣，但我沒有權限，所以會需要主管立刻協助。"
        assert is_question_like(text) is False

        judgment = {
            "confidence": 0.6,
            "is_covered": False,
            "evidence_quote": "客戶現場要我馬上確認折扣",
            "missing_element_ids": ["criterion_1"],
            "covered_element_ids": ["criterion_0"],
            "response_status": "responded",
            "relation": "answer",
        }
        state, act, comp = reduce_card_state("pending", judgment)
        assert state == "probably_sufficient"
        assert act == 1.0
        assert comp == 0.6

    def test_topic_mention_relation_activates_card(self):
        """relation=topic_mention should activate (listening) without progress."""
        judgment = {
            "confidence": 0.0,
            "is_covered": False,
            "evidence_quote": "",
            "missing_element_ids": [],
            "covered_element_ids": [],
            "response_status": "question_only",
            "relation": "topic_mention",
        }
        state, act, comp = reduce_card_state("pending", judgment)
        assert state == "listening"
        assert act == 1.0
        assert comp == 0.0

    def test_question_with_preamble_detected(self):
        """Interviewer-style question with preamble like '我想先詢問' should be detected."""
        text = "我想先詢問一下，就是目前你在銷售過程當中最常需要幫忙的是什麼情境呢？"
        assert is_question_like(text) is True

    def test_answer_with_question_word_not_blocked(self):
        """Real answer containing question words should NOT be blocked."""
        text = "客戶問我能不能馬上給折扣，所以我會先確認公司政策，再找主管協助。"
        assert is_question_like(text) is False


class TestExclusiveActiveCardMode:
    """Tests for exclusive evaluation mode when active_card_id is user-confirmed."""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.add = Mock()
        db.query.return_value.filter.return_value.with_entities.return_value.order_by.return_value.first.return_value = (
            None
        )
        return db

    def test_exclusive_mode_only_evaluates_active_card(self, mock_db):
        """When active_card_id is user_confirmed, only that card should be evaluated."""
        from app.models.interview_session import InterviewSession

        # Mock session with user-confirmed active card
        mock_session = Mock(spec=InterviewSession)
        mock_session.active_card_id = "qcard_active"
        mock_session.active_card_source = "user_confirmed"
        mock_session.active_card_hint_id = "qcard_active"
        mock_session.pending_answer_buffer = None
        mock_session.current_section_id = "theme_1"
        mock_session.current_theme_id = "theme_1"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        with (
            patch.object(answer_evaluation_engine, "_load_candidate_cards") as mock_load,
            patch.object(answer_evaluation_engine, "_batch_judge_answer_sufficiency") as mock_judge,
            patch.object(answer_evaluation_engine, "_build_structured_context") as mock_ctx,
            patch.object(answer_evaluation_engine, "_update_card_state") as mock_update,
            patch("app.services.answer_evaluation_engine.question_rubric_service") as mock_rubric,
        ):
            mock_rubric.get_rubric_if_cached.return_value = {"criteria": []}

            active_card = Mock(
                id="qcard_active", question_text="Q1", focus_text="F1", coverage_rule={}
            )
            active_state = Mock(
                id="s1", status="listening", session_id="session_1", question_card_id="qcard_active"
            )
            mock_load.return_value = [{"card": active_card, "state": active_state}]
            mock_ctx.return_value = "context"
            mock_judge.return_value = [
                {"confidence": 0.5, "is_covered": False, "response_status": "responded"}
            ]
            mock_update.return_value = {
                "card_id": "qcard_active",
                "new_status": "probably_sufficient",
            }

            updates = answer_evaluation_engine._evaluate_answer(
                mock_db, "session_1", "utt_1", "回答內容", "theme_1", "interviewee"
            )

            # _load_candidate_cards should be called with active_card_id filter
            mock_load.assert_called_once_with(
                mock_db,
                "session_1",
                "theme_1",
                active_card_id="qcard_active",
                statuses=["listening", "probably_sufficient", "at_risk"],
            )
            assert len(updates) == 1
            assert updates[0]["card_id"] == "qcard_active"

    def test_exclusive_mode_does_not_evaluate_other_cards(self, mock_db):
        """Other pending cards should not receive any completion in exclusive mode."""
        from app.models.interview_session import InterviewSession

        mock_session = Mock(spec=InterviewSession)
        mock_session.active_card_id = "qcard_active"
        mock_session.active_card_source = "user_confirmed"
        mock_session.active_card_hint_id = "qcard_active"
        mock_session.pending_answer_buffer = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        with (patch.object(answer_evaluation_engine, "_load_candidate_cards") as mock_load,):
            # Active card not in evaluable state (e.g., already sufficient)
            mock_load.return_value = []

            updates = answer_evaluation_engine._evaluate_answer(
                mock_db, "session_1", "utt_1", "回答內容", "theme_1", "interviewee"
            )

            # No updates should happen — other cards are NOT evaluated
            assert updates == []

    def test_non_exclusive_when_no_active_card(self, mock_db):
        """Without active_card_id, system evaluates all candidates (legacy mode)."""
        from app.models.interview_session import InterviewSession

        mock_session = Mock(spec=InterviewSession)
        mock_session.active_card_id = None
        mock_session.active_card_source = None
        mock_session.active_card_hint_id = None
        mock_session.pending_answer_buffer = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        with (
            patch.object(answer_evaluation_engine, "_load_candidate_cards") as mock_load,
            patch.object(answer_evaluation_engine, "_prefilter_candidates") as mock_filter,
            patch.object(answer_evaluation_engine, "_batch_judge_answer_sufficiency") as mock_judge,
            patch.object(answer_evaluation_engine, "_build_structured_context") as mock_ctx,
            patch.object(answer_evaluation_engine, "_update_card_state") as mock_update,
            patch("app.services.answer_evaluation_engine.question_rubric_service") as mock_rubric,
        ):
            mock_rubric.get_rubric_if_cached.return_value = {"criteria": []}
            card1 = Mock(id="qcard_1", question_text="Q1", focus_text="F1", coverage_rule={})
            state1 = Mock(
                id="s1", status="pending", session_id="session_1", question_card_id="qcard_1"
            )
            card2 = Mock(id="qcard_2", question_text="Q2", focus_text="F2", coverage_rule={})
            state2 = Mock(
                id="s2", status="pending", session_id="session_1", question_card_id="qcard_2"
            )

            mock_load.return_value = [
                {"card": card1, "state": state1},
                {"card": card2, "state": state2},
            ]
            mock_filter.return_value = [
                {"card": card1, "state": state1},
                {"card": card2, "state": state2},
            ]
            mock_ctx.return_value = "context"
            mock_judge.return_value = [
                {"confidence": 0.5, "is_covered": False, "response_status": "responded"},
                {"confidence": 0.3, "is_covered": False, "response_status": "responded"},
            ]
            mock_update.side_effect = [
                {"card_id": "qcard_1", "new_status": "probably_sufficient"},
                None,  # second card blocked by one-pending rule
            ]

            updates = answer_evaluation_engine._evaluate_answer(
                mock_db, "session_1", "utt_1", "回答內容", "theme_1", "interviewee"
            )

            # In non-exclusive mode, multiple cards are loaded/filtered
            mock_load.assert_called_once()
            mock_filter.assert_called_once()

    def test_cleared_active_card_returns_to_non_exclusive(self, mock_db):
        """After clearing active card (source='cleared'), system returns to non-exclusive."""
        from app.models.interview_session import InterviewSession

        mock_session = Mock(spec=InterviewSession)
        mock_session.active_card_id = None
        mock_session.active_card_source = "cleared"
        mock_session.active_card_hint_id = None
        mock_session.pending_answer_buffer = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        with (
            patch.object(answer_evaluation_engine, "_load_candidate_cards") as mock_load,
            patch.object(answer_evaluation_engine, "_prefilter_candidates") as mock_filter,
            patch.object(answer_evaluation_engine, "_batch_judge_answer_sufficiency") as mock_judge,
            patch.object(answer_evaluation_engine, "_build_structured_context") as mock_ctx,
            patch("app.services.answer_evaluation_engine.question_rubric_service") as mock_rubric,
        ):
            mock_rubric.get_rubric_if_cached.return_value = {"criteria": []}
            mock_load.return_value = []
            mock_filter.return_value = []

            answer_evaluation_engine._evaluate_answer(
                mock_db, "session_1", "utt_1", "回答", "theme_1", "interviewee"
            )

            # Should use non-exclusive path (load all candidates, prefilter)
            mock_load.assert_called_once_with(
                mock_db,
                "session_1",
                "theme_1",
                statuses=["pending", "listening", "probably_sufficient", "at_risk"],
            )
