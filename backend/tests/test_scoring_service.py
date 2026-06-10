"""
Unit tests for Scoring Service
Tests keyword, fact, and final score calculations.
"""

import pytest

from app.services.scoring_service import scoring_service, ScoringService


class TestScoringService:
    """Test suite for scoring service."""

    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        assert scoring_service is not None
        assert isinstance(scoring_service, ScoringService)

    # --- normalize_text ---

    def test_normalize_text_lowercase(self):
        assert scoring_service.normalize_text("Hello World") == "hello world"

    def test_normalize_text_removes_punctuation(self):
        assert scoring_service.normalize_text("Hello, World!") == "hello world"
        result = scoring_service.normalize_text("Test. Item? Yes!")
        assert "." not in result
        assert "?" not in result
        assert "!" not in result

    def test_normalize_text_chinese_punctuation(self):
        result = scoring_service.normalize_text("你好，世界！")
        assert "，" not in result
        assert "！" not in result

    def test_normalize_text_empty(self):
        assert scoring_service.normalize_text("") == ""
        assert scoring_service.normalize_text(None) == ""

    def test_normalize_text_whitespace(self):
        result = scoring_service.normalize_text("  hello   world  ")
        assert result == "hello world"

    # --- calculate_keyword_score ---

    def test_keyword_score_all_matched(self):
        score = scoring_service.calculate_keyword_score(
            "今天介紹機器學習和深度學習",
            ["機器學習", "深度學習"]
        )
        assert score == 1.0

    def test_keyword_score_partial_match(self):
        score = scoring_service.calculate_keyword_score(
            "今天介紹機器學習",
            ["機器學習", "深度學習", "神經網路"]
        )
        assert score == pytest.approx(1/3, abs=0.01)

    def test_keyword_score_no_match(self):
        score = scoring_service.calculate_keyword_score(
            "completely unrelated text",
            ["機器學習", "深度學習"]
        )
        assert score == 0.0

    def test_keyword_score_empty_keywords(self):
        score = scoring_service.calculate_keyword_score(
            "some text",
            []
        )
        assert score == 1.0

    def test_keyword_score_empty_utterance(self):
        score = scoring_service.calculate_keyword_score(
            "",
            ["keyword1", "keyword2"]
        )
        assert score == 0.0

    def test_keyword_score_case_insensitive(self):
        score = scoring_service.calculate_keyword_score(
            "Machine Learning is great",
            ["machine learning"]
        )
        assert score == 1.0

    def test_keyword_score_two_of_three(self):
        score = scoring_service.calculate_keyword_score(
            "今天介紹機器學習和深度學習",
            ["機器學習", "深度學習", "神經網路"]
        )
        assert score == pytest.approx(2/3, abs=0.01)

    # --- calculate_fact_score ---

    def test_fact_score_all_required_matched(self):
        facts = [
            {"text": "92%準確率", "required": True, "aliases": ["92%"]},
            {"text": "降低成本", "required": True}
        ]
        score = scoring_service.calculate_fact_score(
            "達到92%準確率並降低成本",
            facts
        )
        assert score == 1.0

    def test_fact_score_partial_required(self):
        facts = [
            {"text": "revenue", "required": True},
            {"text": "cost", "required": True}
        ]
        score = scoring_service.calculate_fact_score(
            "we increased revenue significantly",
            facts
        )
        assert score == 0.5

    def test_fact_score_with_aliases(self):
        facts = [
            {"text": "收入", "required": True, "aliases": ["revenue", "income"]}
        ]
        score = scoring_service.calculate_fact_score(
            "our income grew by 20%",
            facts
        )
        assert score == 1.0

    def test_fact_score_empty_facts(self):
        score = scoring_service.calculate_fact_score("some text", [])
        assert score == 1.0

    def test_fact_score_empty_utterance(self):
        facts = [{"text": "test", "required": True}]
        score = scoring_service.calculate_fact_score("", facts)
        assert score == 0.0

    def test_fact_score_optional_only(self):
        facts = [
            {"text": "optional fact", "required": False}
        ]
        score = scoring_service.calculate_fact_score(
            "this is an optional fact",
            facts
        )
        assert score == 1.0

    def test_fact_score_mixed_required_optional(self):
        facts = [
            {"text": "required item", "required": True},
            {"text": "optional item", "required": False}
        ]
        score = scoring_service.calculate_fact_score(
            "this has the required item",
            facts
        )
        # required_score = 1.0, optional_score = 0.0
        # final = 1.0 * 0.8 + 0.0 * 0.2 = 0.8
        assert score == pytest.approx(0.8, abs=0.01)

    def test_fact_score_with_subpoints(self):
        facts = [
            {"text": "top stocks", "required": True, "subpoints": ["台積電", "聯電"]}
        ]
        # All subpoints must be mentioned
        score = scoring_service.calculate_fact_score(
            "台積電和聯電是重要的",
            facts
        )
        assert score == 1.0

    def test_fact_score_partial_subpoints(self):
        facts = [
            {"text": "top stocks", "required": True, "subpoints": ["台積電", "聯電", "華邦電"]}
        ]
        # Only 2 of 3 subpoints
        score = scoring_service.calculate_fact_score(
            "台積電和聯電是重要的",
            facts
        )
        assert score == 0.0  # All subpoints must match

    # --- _is_fact_mentioned ---

    def test_is_fact_mentioned_direct(self):
        assert scoring_service._is_fact_mentioned(
            "we have revenue growth",
            {"text": "revenue growth"}
        ) is True

    def test_is_fact_mentioned_alias(self):
        assert scoring_service._is_fact_mentioned(
            "our income is growing",
            {"text": "revenue", "aliases": ["income", "earnings"]}
        ) is True

    def test_is_fact_mentioned_not_found(self):
        assert scoring_service._is_fact_mentioned(
            "completely different text",
            {"text": "revenue", "aliases": []}
        ) is False

    def test_is_fact_mentioned_subpoints_all(self):
        assert scoring_service._is_fact_mentioned(
            "台積電 and 聯電 are important",
            {"text": "stocks", "subpoints": ["台積電", "聯電"]}
        ) is True

    def test_is_fact_mentioned_subpoints_missing(self):
        assert scoring_service._is_fact_mentioned(
            "台積電 is important",
            {"text": "stocks", "subpoints": ["台積電", "聯電"]}
        ) is False

    # --- calculate_final_score ---

    def test_final_score_default_weights(self):
        score = scoring_service.calculate_final_score(0.85, 0.67, 1.0)
        # 0.85*0.55 + 0.67*0.25 + 1.0*0.20 = 0.4675 + 0.1675 + 0.20 = 0.835
        assert score == pytest.approx(0.835, abs=0.01)

    def test_final_score_all_zeros(self):
        score = scoring_service.calculate_final_score(0.0, 0.0, 0.0)
        assert score == 0.0

    def test_final_score_all_ones(self):
        score = scoring_service.calculate_final_score(1.0, 1.0, 1.0)
        assert score == 1.0

    def test_final_score_custom_weights(self):
        weights = {
            'semanticSimilarity': 0.5,
            'keywordCoverage': 0.3,
            'factCoverage': 0.2
        }
        score = scoring_service.calculate_final_score(1.0, 0.0, 0.0, weights)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_final_score_clamped_to_one(self):
        # Even with values > 1 (shouldn't happen), clamped
        score = scoring_service.calculate_final_score(1.5, 1.5, 1.5)
        assert score <= 1.0

    def test_final_score_clamped_to_zero(self):
        score = scoring_service.calculate_final_score(-0.5, -0.5, -0.5)
        assert score >= 0.0

    # --- determine_status ---

    def test_determine_status_covered(self):
        status = scoring_service.determine_status(0.85)
        assert status == 'covered'

    def test_determine_status_probably_covered(self):
        status = scoring_service.determine_status(0.60)
        assert status == 'probably_covered'

    def test_determine_status_pending(self):
        status = scoring_service.determine_status(0.30)
        assert status == 'pending'

    def test_determine_status_at_threshold(self):
        status = scoring_service.determine_status(0.70)
        assert status == 'covered'

    def test_determine_status_custom_thresholds(self):
        thresholds = {'covered': 0.90, 'probablyCovered': 0.70}
        status = scoring_service.determine_status(0.80, thresholds)
        assert status == 'probably_covered'

    def test_determine_status_zero(self):
        status = scoring_service.determine_status(0.0)
        assert status == 'pending'

    def test_determine_status_one(self):
        status = scoring_service.determine_status(1.0)
        assert status == 'covered'
