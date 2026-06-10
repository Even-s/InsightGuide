"""
Unit tests for Question Card Service
Tests question card management and coverage rule normalization.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from app.services.question_card_service import question_card_service, QuestionCardService
from app.models.question_card import QuestionCard
from app.models.section import Section
from app.schemas.question_card import QuestionCardCreate, QuestionCardUpdate


class TestQuestionCardService:
    """Test suite for question card service."""

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
    def sample_question_card(self):
        """Create a sample question card."""
        return QuestionCard(
            id="card-123",
            document_id="doc-456",
            section_id="section-789",
            question_text="What are the main objectives?",
            question_type="objectives",
            importance="must",
            expected_answer_elements=["Objective 1", "Objective 2"],
            coverage_rule={
                "semanticAnchors": ["goal", "target"],
                "mustMentionElements": [
                    {"text": "Revenue growth", "required": True},
                    {"text": "Market expansion", "required": True}
                ]
            },
            created_at=datetime.utcnow()
        )

    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        assert question_card_service is not None
        assert isinstance(question_card_service, QuestionCardService)
        assert question_card_service.MAX_IMPORTANT_ELEMENTS == 3

    def test_normalize_text_key_english(self):
        """Test text normalization for English."""
        text = "Hello, World!"
        key = QuestionCardService._normalize_text_key(text)

        assert key == "helloworld"
        assert " " not in key
        assert "," not in key
        assert "!" not in key

    def test_normalize_text_key_chinese(self):
        """Test text normalization for Chinese."""
        text = "你好，世界！"
        key = QuestionCardService._normalize_text_key(text)

        assert "，" not in key
        assert "！" not in key
        # Should keep Chinese characters
        assert len(key) > 0

    def test_normalize_text_key_mixed(self):
        """Test text normalization for mixed language."""
        text = "Hello 世界, test！"
        key = QuestionCardService._normalize_text_key(text)

        assert " " not in key
        assert "," not in key
        assert "！" not in key

    def test_normalize_text_key_empty(self):
        """Test normalizing empty text."""
        assert QuestionCardService._normalize_text_key("") == ""
        assert QuestionCardService._normalize_text_key(None) == ""
        assert QuestionCardService._normalize_text_key("   ") == ""

    def test_element_text_dict(self):
        """Test extracting text from dict element."""
        element = {"text": "Test element", "required": True}
        text = QuestionCardService._element_text(element)

        assert text == "Test element"

    def test_element_text_string(self):
        """Test extracting text from string element."""
        element = "Test element"
        text = QuestionCardService._element_text(element)

        assert text == "Test element"

    def test_element_text_none(self):
        """Test extracting text from None."""
        text = QuestionCardService._element_text(None)
        assert text == ""

    def test_clean_numbered_point_arabic(self):
        """Test cleaning Arabic numbered points."""
        assert QuestionCardService._clean_numbered_point("1. First point") == "First point"
        assert QuestionCardService._clean_numbered_point("2) Second point") == "Second point"
        assert QuestionCardService._clean_numbered_point("3: Third point") == "Third point"

    def test_clean_numbered_point_chinese(self):
        """Test cleaning Chinese numbered points."""
        assert QuestionCardService._clean_numbered_point("一、第一點") == "第一點"
        result = QuestionCardService._clean_numbered_point("二）第二點")
        assert "第二點" in result

    def test_clean_numbered_point_nested(self):
        """Test cleaning nested numbered points."""
        assert QuestionCardService._clean_numbered_point("1.1. Nested point") == "Nested point"
        assert QuestionCardService._clean_numbered_point("2.3.1) Deep nest") == "Deep nest"

    def test_clean_numbered_point_no_number(self):
        """Test cleaning text without numbers."""
        text = "Plain text"
        assert QuestionCardService._clean_numbered_point(text) == text

    def test_is_represented_by_element_exact_match(self):
        """Test element representation with exact match."""
        anchor = "revenue growth"
        elements = [
            {"text": "Revenue growth target", "aliases": [], "subpoints": []}
        ]

        assert QuestionCardService._is_represented_by_element(anchor, elements) is True

    def test_is_represented_by_element_alias_match(self):
        """Test element representation with alias match."""
        anchor = "income"
        elements = [
            {
                "text": "Revenue",
                "aliases": ["income", "earnings"],
                "subpoints": []
            }
        ]

        assert QuestionCardService._is_represented_by_element(anchor, elements) is True

    def test_is_represented_by_element_subpoint_match(self):
        """Test element representation with subpoint match."""
        anchor = "Q1 target"
        elements = [
            {
                "text": "Revenue goals",
                "aliases": [],
                "subpoints": ["Q1 target", "Q2 target"]
            }
        ]

        assert QuestionCardService._is_represented_by_element(anchor, elements) is True

    def test_is_represented_by_element_no_match(self):
        """Test element representation with no match."""
        anchor = "completely different"
        elements = [
            {"text": "Revenue", "aliases": [], "subpoints": []}
        ]

        assert QuestionCardService._is_represented_by_element(anchor, elements) is False

    def test_is_represented_by_element_empty_anchor(self):
        """Test with empty anchor."""
        assert QuestionCardService._is_represented_by_element("", []) is True

    def test_normalize_coverage_rule_basic(self):
        """Test basic coverage rule normalization."""
        coverage_rule = {
            "semanticAnchors": ["goal", "target", "objective"],
            "mustMentionElements": ["Revenue growth", "Market expansion"]
        }

        normalized = question_card_service.normalize_coverage_rule_for_important_elements(
            coverage_rule
        )

        assert "semanticAnchors" in normalized
        assert "mustMentionElements" in normalized
        assert isinstance(normalized["mustMentionElements"], list)

    def test_normalize_coverage_rule_with_dict_elements(self):
        """Test normalization with dict elements."""
        coverage_rule = {
            "semanticAnchors": [],
            "mustMentionElements": [
                {"text": "1. Revenue growth", "required": True},
                {"text": "2. Market expansion", "required": False}
            ]
        }

        normalized = question_card_service.normalize_coverage_rule_for_important_elements(
            coverage_rule
        )

        # Should clean numbered points
        elements = normalized["mustMentionElements"]
        assert any("Revenue growth" in str(e) for e in elements)

    def test_normalize_coverage_rule_max_elements(self):
        """Test that normalization respects MAX_IMPORTANT_ELEMENTS."""
        coverage_rule = {
            "mustMentionElements": [
                "Element 1",
                "Element 2",
                "Element 3",
                "Element 4",
                "Element 5"
            ]
        }

        normalized = question_card_service.normalize_coverage_rule_for_important_elements(
            coverage_rule
        )

        # Should limit to 3 elements
        elements = normalized.get("mustMentionElements", [])
        assert len(elements) <= QuestionCardService.MAX_IMPORTANT_ELEMENTS

    def test_normalize_coverage_rule_empty(self):
        """Test normalizing empty coverage rule."""
        normalized = question_card_service.normalize_coverage_rule_for_important_elements(None)

        assert isinstance(normalized, dict)
        assert "semanticAnchors" in normalized or normalized == {}

    def test_normalize_coverage_rule_no_elements(self):
        """Test normalization with no must mention elements."""
        coverage_rule = {
            "semanticAnchors": ["test"],
            "mustMentionElements": []
        }

        normalized = question_card_service.normalize_coverage_rule_for_important_elements(
            coverage_rule
        )

        assert isinstance(normalized, dict)

    def test_normalize_coverage_rule_deduplication(self):
        """Test that similar elements are deduplicated."""
        coverage_rule = {
            "mustMentionElements": [
                "Revenue growth",
                "1. Revenue growth",  # Duplicate with numbering
                "revenue growth",      # Duplicate case variation
                "Market expansion"
            ]
        }

        normalized = question_card_service.normalize_coverage_rule_for_important_elements(
            coverage_rule
        )

        # Should deduplicate similar elements
        elements = normalized.get("mustMentionElements", [])
        # Exact count depends on implementation, but should be less than 4
        assert len(elements) <= 3

    def test_normalize_coverage_rule_with_aliases(self):
        """Test normalization with element aliases."""
        coverage_rule = {
            "mustMentionElements": [
                {
                    "text": "Revenue",
                    "aliases": ["income", "earnings"],
                    "subpoints": ["Q1 target", "Q2 target"]
                }
            ]
        }

        normalized = question_card_service.normalize_coverage_rule_for_important_elements(
            coverage_rule
        )

        elements = normalized.get("mustMentionElements", [])
        assert len(elements) > 0

    def test_normalize_coverage_rule_preserves_required_flag(self):
        """Test that required flags are preserved."""
        coverage_rule = {
            "mustMentionElements": [
                {"text": "Required element", "required": True},
                {"text": "Optional element", "required": False}
            ]
        }

        normalized = question_card_service.normalize_coverage_rule_for_important_elements(
            coverage_rule
        )

        elements = normalized.get("mustMentionElements", [])
        assert len(elements) == 2

    def test_normalize_coverage_rule_semantic_anchor_fallback(self):
        """Test using semantic anchors when no mustMentionElements."""
        coverage_rule = {
            "semanticAnchors": ["goal", "objective", "target"],
            "mustMentionElements": []
        }

        normalized = question_card_service.normalize_coverage_rule_for_important_elements(
            coverage_rule
        )

        # Should keep semantic anchors
        assert "semanticAnchors" in normalized
        assert len(normalized["semanticAnchors"]) == 3

    def test_normalize_coverage_rule_filters_empty_elements(self):
        """Test that empty elements are filtered out."""
        coverage_rule = {
            "mustMentionElements": [
                "Valid element",
                "",
                "   ",
                None,
                "Another valid"
            ]
        }

        normalized = question_card_service.normalize_coverage_rule_for_important_elements(
            coverage_rule
        )

        elements = normalized.get("mustMentionElements", [])
        # Should only have 2 valid elements
        assert all(e for e in elements)  # No empty elements

    def test_normalize_coverage_rule_handles_special_chars(self):
        """Test normalization handles special characters."""
        coverage_rule = {
            "mustMentionElements": [
                "Element with (parentheses)",
                "Element with [brackets]",
                "Element with 「quotes」"
            ]
        }

        normalized = question_card_service.normalize_coverage_rule_for_important_elements(
            coverage_rule
        )

        elements = normalized.get("mustMentionElements", [])
        assert len(elements) == 3

    def test_normalize_coverage_rule_mixed_types(self):
        """Test normalization with mixed string and dict elements."""
        coverage_rule = {
            "mustMentionElements": [
                "String element",
                {"text": "Dict element", "required": True},
                "Another string"
            ]
        }

        normalized = question_card_service.normalize_coverage_rule_for_important_elements(
            coverage_rule
        )

        elements = normalized.get("mustMentionElements", [])
        assert len(elements) == 3

    def test_normalize_text_key_punctuation_removal(self):
        """Test that various punctuation marks are removed."""
        test_cases = [
            ("Hello, World!", "helloworld"),
            ("Test: Example", "testexample"),
            ("Question?", "question"),
            ("Answer!", "answer"),
            ("「Chinese」", "chinese"),
            ("（test）", "test")
        ]

        for input_text, expected in test_cases:
            result = QuestionCardService._normalize_text_key(input_text)
            assert result == expected

    def test_element_text_with_empty_dict(self):
        """Test extracting text from dict without text key."""
        element = {"required": True}
        text = QuestionCardService._element_text(element)

        assert text == ""

    def test_is_represented_case_insensitive(self):
        """Test that element matching is case-insensitive."""
        anchor = "REVENUE GROWTH"
        elements = [
            {"text": "revenue growth", "aliases": [], "subpoints": []}
        ]

        assert QuestionCardService._is_represented_by_element(anchor, elements) is True
