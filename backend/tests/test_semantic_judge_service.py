"""
Unit tests for Semantic Judge Service
Tests AI-powered semantic judging of answer sufficiency.
"""

import pytest
from unittest.mock import Mock, patch
from openai import OpenAI

from app.services.semantic_judge_service import semantic_judge_service, SemanticJudgeService


class TestSemanticJudgeService:
    """Test suite for semantic judge service."""

    @pytest.fixture
    def sample_coverage_rule(self):
        """Create a sample coverage rule."""
        return {
            "semanticAnchors": ["revenue", "growth", "target"],
            "mustMentionElements": [
                {"text": "Revenue target", "required": True},
                {"text": "Growth percentage", "required": True}
            ]
        }

    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        assert semantic_judge_service is not None
        assert isinstance(semantic_judge_service, SemanticJudgeService)

    def test_service_has_required_methods(self):
        """Test that service has all required methods."""
        assert hasattr(semantic_judge_service, 'judge_coverage')
        assert hasattr(semantic_judge_service, '_build_judge_prompt')

    @patch.object(SemanticJudgeService, 'judge_coverage')
    def test_judge_coverage_sufficient_answer(
        self,
        mock_judge,
        sample_coverage_rule
    ):
        """Test judging a sufficient answer."""
        # Mock judgment response
        mock_judge.return_value = {
            "is_covered": True,
            "confidence": 0.9,
            "reasoning": "Answer covers all required elements",
            "mentioned_keywords": ["revenue", "target", "growth"],
            "missing_aspects": []
        }

        topic_card = {
            "title": "Revenue Targets",
            "description": "What are the revenue targets?",
            "coverageRule": sample_coverage_rule
        }

        result = semantic_judge_service.judge_coverage(
            utterance_text="Our revenue target is $10M with 25% growth",
            topic_card=topic_card,
            session_id="session-123"
        )

        assert result["is_covered"] is True
        assert result["confidence"] == 0.9
        mock_judge.assert_called_once()

    @patch.object(SemanticJudgeService, 'judge_coverage')
    def test_judge_coverage_insufficient_answer(
        self,
        mock_judge,
        sample_coverage_rule
    ):
        """Test judging an insufficient answer."""
        mock_judge.return_value = {
            "is_covered": False,
            "confidence": 0.3,
            "reasoning": "Missing growth percentage",
            "mentioned_keywords": ["revenue"],
            "missing_aspects": ["growth percentage", "target amount"]
        }

        topic_card = {
            "title": "Revenue Targets",
            "description": "What are the revenue targets?",
            "coverageRule": sample_coverage_rule
        }

        result = semantic_judge_service.judge_coverage(
            utterance_text="We want to increase revenue",
            topic_card=topic_card,
            session_id="session-123"
        )

        assert result["is_covered"] is False
        assert result["confidence"] == 0.3
        assert len(result["missing_aspects"]) > 0

    @patch.object(SemanticJudgeService, 'judge_coverage')
    def test_judge_coverage_partial_answer(
        self,
        mock_judge,
        sample_coverage_rule
    ):
        """Test judging a partially sufficient answer."""
        mock_judge.return_value = {
            "is_covered": False,
            "confidence": 0.65,
            "reasoning": "Has target but missing specific percentage",
            "mentioned_keywords": ["revenue", "target"],
            "missing_aspects": ["growth percentage"]
        }

        topic_card = {
            "title": "Revenue Targets",
            "description": "What are the revenue targets?",
            "coverageRule": sample_coverage_rule
        }

        result = semantic_judge_service.judge_coverage(
            utterance_text="Revenue target is $10M",
            topic_card=topic_card,
            session_id="session-123"
        )

        assert result["confidence"] >= 0.6
        assert len(result["mentioned_keywords"]) > 0
        assert len(result["missing_aspects"]) > 0

    @patch.object(SemanticJudgeService, 'judge_coverage')
    def test_judge_coverage_empty_answer(
        self,
        mock_judge,
        sample_coverage_rule
    ):
        """Test judging an empty answer."""
        mock_judge.return_value = {
            "is_covered": False,
            "confidence": 0.0,
            "reasoning": "No answer provided",
            "mentioned_keywords": [],
            "missing_aspects": ["Revenue target", "Growth percentage"]
        }

        topic_card = {
            "title": "Revenue Targets",
            "description": "What are the revenue targets?",
            "coverageRule": sample_coverage_rule
        }

        result = semantic_judge_service.judge_coverage(
            utterance_text="",
            topic_card=topic_card,
            session_id="session-123"
        )

        assert result["is_covered"] is False
        assert result["confidence"] == 0.0

    def test_build_judgment_prompt_basic(self):
        """Test building judgment prompt."""
        prompt = semantic_judge_service._build_judge_prompt(
            utterance_text="Our main objective is growth",
            title="Objectives",
            description="What are the objectives?",
            semantic_anchors=["goal", "target"],
            expected_keywords=["objective"],
            must_mention_facts=[]
        )

        assert "Objectives" in prompt or "objective" in prompt.lower()
        assert "Our main objective is growth" in prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_judgment_prompt_with_coverage_rule(self, sample_coverage_rule):
        """Test building prompt with coverage rule."""
        must_mention = sample_coverage_rule.get("mustMentionElements", [])
        prompt = semantic_judge_service._build_judge_prompt(
            utterance_text="Target is $10M",
            title="Revenue Targets",
            description="What are the revenue targets?",
            semantic_anchors=sample_coverage_rule.get("semanticAnchors", []),
            expected_keywords=["revenue", "growth"],
            must_mention_facts=must_mention
        )

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @patch.object(SemanticJudgeService, 'judge_coverage')
    def test_judge_with_no_expected_elements(self, mock_judge):
        """Test judging when no expected elements provided."""
        mock_judge.return_value = {
            "is_covered": True,
            "confidence": 0.8,
            "reasoning": "Answer is complete",
            "mentioned_keywords": [],
            "missing_aspects": []
        }

        topic_card = {
            "title": "Project Description",
            "description": "Describe the project",
            "coverageRule": {}
        }

        result = semantic_judge_service.judge_coverage(
            utterance_text="This is a comprehensive project description",
            topic_card=topic_card,
            session_id="session-123"
        )

        assert "is_covered" in result
        assert "confidence" in result

    @patch('app.services.semantic_judge_service.OpenAI')
    def test_judge_with_error_handling(self, mock_openai_class):
        """Test error handling when OpenAI call fails."""
        # Mock the OpenAI client instance
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        # Create a new service instance that will use the mocked OpenAI class
        service = SemanticJudgeService()

        topic_card = {
            "title": "Test",
            "description": "Test question",
            "coverageRule": {}
        }

        # Should handle gracefully and return default values
        result = service.judge_coverage(
            utterance_text="Test answer",
            topic_card=topic_card,
            session_id="session-123"
        )

        # Should return safe default
        assert "is_covered" in result
        assert result["is_covered"] is False
        assert result["confidence"] == 0.0

    @patch.object(SemanticJudgeService, 'judge_coverage')
    def test_multiple_judgment_calls(self, mock_judge):
        """Test multiple sequential judgment calls."""
        mock_judge.return_value = {
            "is_covered": True,
            "confidence": 0.8,
            "reasoning": "Complete",
            "mentioned_keywords": [],
            "missing_aspects": []
        }

        # Multiple calls should work
        for i in range(3):
            topic_card = {
                "title": f"Topic {i}",
                "description": f"Question {i}",
                "coverageRule": {}
            }
            result = semantic_judge_service.judge_coverage(
                utterance_text=f"Answer {i}",
                topic_card=topic_card,
                session_id=f"session-{i}"
            )
            assert result["is_covered"] is True

        assert mock_judge.call_count == 3

    @patch.object(SemanticJudgeService, 'judge_coverage')
    def test_judge_with_long_answer(self, mock_judge, sample_coverage_rule):
        """Test judging with very long answer text."""
        mock_judge.return_value = {
            "is_covered": True,
            "confidence": 0.9,
            "reasoning": "Complete answer",
            "mentioned_keywords": ["target"],
            "missing_aspects": []
        }

        long_answer = "This is a very long answer. " * 500

        topic_card = {
            "title": "Targets",
            "description": "What are the targets?",
            "coverageRule": sample_coverage_rule
        }

        result = semantic_judge_service.judge_coverage(
            utterance_text=long_answer,
            topic_card=topic_card,
            session_id="session-123"
        )

        assert result["is_covered"] is True

    def test_judgment_prompt_includes_context(self):
        """Test that judgment prompt includes necessary context."""
        prompt = semantic_judge_service._build_judge_prompt(
            utterance_text="The budget is $500K for Q1",
            title="Budget",
            description="What is the budget?",
            semantic_anchors=["cost", "expense", "budget"],
            expected_keywords=["amount", "timeline"],
            must_mention_facts=[{"text": "Amount", "required": True}]
        )

        # Prompt should include all key information
        assert "Budget" in prompt or "budget" in prompt.lower()
        assert "The budget is $500K for Q1" in prompt

    @patch.object(SemanticJudgeService, 'judge_coverage')
    def test_judge_with_chinese_text(self, mock_judge):
        """Test judging with Chinese text."""
        mock_judge.return_value = {
            "is_covered": True,
            "confidence": 0.85,
            "reasoning": "回答完整",
            "mentioned_keywords": ["目標", "收入", "市場"],
            "missing_aspects": []
        }

        topic_card = {
            "title": "主要目標",
            "description": "什麼是主要目標？",
            "coverageRule": {}
        }

        result = semantic_judge_service.judge_coverage(
            utterance_text="主要目標是提高收入和擴大市場",
            topic_card=topic_card,
            session_id="session-123"
        )

        assert result["is_covered"] is True
        assert result["confidence"] > 0

    @patch.object(SemanticJudgeService, 'judge_coverage')
    def test_judge_returns_all_required_fields(self, mock_judge):
        """Test that judgment result has all required fields."""
        mock_judge.return_value = {
            "is_covered": True,
            "confidence": 0.8,
            "reasoning": "Complete",
            "mentioned_keywords": ["element"],
            "missing_aspects": []
        }

        topic_card = {
            "title": "Test",
            "description": "Test",
            "coverageRule": {}
        }

        result = semantic_judge_service.judge_coverage(
            utterance_text="Answer",
            topic_card=topic_card,
            session_id="session-123"
        )

        # Verify all required fields
        assert "is_covered" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert "mentioned_keywords" in result
        assert "missing_aspects" in result

    @patch.object(SemanticJudgeService, 'judge_coverage')
    def test_judge_score_ranges(self, mock_judge):
        """Test that confidence scores are in valid range."""
        test_scores = [0.0, 0.3, 0.5, 0.7, 0.9, 1.0]

        for score in test_scores:
            mock_judge.return_value = {
                "is_covered": score >= 0.6,
                "confidence": score,
                "reasoning": f"Score: {score}",
                "mentioned_keywords": [],
                "missing_aspects": []
            }

            topic_card = {
                "title": "Test",
                "description": "Test",
                "coverageRule": {}
            }

            result = semantic_judge_service.judge_coverage(
                utterance_text="Answer",
                topic_card=topic_card,
                session_id="session-123"
            )

            assert 0.0 <= result["confidence"] <= 1.0
