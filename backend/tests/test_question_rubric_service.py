"""
Unit tests for Question Rubric Service.
Tests rubric compilation from existing elements and LLM generation.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from app.models.question_card import QuestionCard
from app.services.question_rubric_service import QuestionRubricService


class TestCompileRubricFromElements:
    """Test conversion of mustMentionElements to criteria format."""

    def setup_method(self):
        self.service = QuestionRubricService()

    def _make_card(self, elements=None, anchors=None, question_text="測試問題"):
        card = Mock(spec=QuestionCard)
        card.id = "card-1"
        card.question_text = question_text
        card.focus_text = "重點"
        card.question_type = "value_slot"
        card.coverage_rule = {
            "mustMentionElements": elements or [],
            "semanticAnchors": anchors or [],
        }
        return card

    def test_single_element_expands_to_multiple_criteria(self):
        """Single element should expand to 2-3 criteria for better granularity."""
        card = self._make_card(elements=[{"text": "最花時間的步驟"}])
        rubric = self.service.compile_rubric_from_elements(card)

        assert rubric["rubricVersion"] == "v1"
        assert len(rubric["criteria"]) >= 2
        assert rubric["criteria"][0]["critical"] is True
        assert rubric["criteria"][0]["weight"] > rubric["criteria"][1]["weight"]
        total_weight = sum(c["weight"] for c in rubric["criteria"])
        assert abs(total_weight - 1.0) < 0.01

    def test_multiple_elements_distribute_weight(self):
        card = self._make_card(
            elements=[
                {"text": "步驟名稱"},
                {"text": "耗時原因"},
            ]
        )
        rubric = self.service.compile_rubric_from_elements(card)

        assert len(rubric["criteria"]) == 2
        assert rubric["criteria"][0]["critical"] is True
        assert rubric["criteria"][1]["critical"] is False
        assert rubric["criteria"][0]["weight"] == 0.5
        assert rubric["criteria"][1]["weight"] == 0.5

    def test_string_elements_handled(self):
        card = self._make_card(elements=["步驟名稱", "耗時原因"])
        rubric = self.service.compile_rubric_from_elements(card)

        assert len(rubric["criteria"]) == 2
        assert "步驟名稱" in rubric["criteria"][0]["description"]

    def test_semantic_anchors_fallback(self):
        card = self._make_card(elements=[], anchors=["anchor1", "anchor2"])
        rubric = self.service.compile_rubric_from_elements(card)

        assert len(rubric["criteria"]) == 2

    def test_answer_target_from_question_text(self):
        card = self._make_card(
            elements=[{"text": "步驟"}], question_text="目前最花時間的環節是什麼？"
        )
        rubric = self.service.compile_rubric_from_elements(card)

        assert rubric["answerTarget"] == "目前最花時間的環節是什麼？"

    def test_criterion_ids_sequential(self):
        card = self._make_card(elements=[{"text": "a"}, {"text": "b"}, {"text": "c"}])
        rubric = self.service.compile_rubric_from_elements(card)

        assert rubric["criteria"][0]["id"] == "criterion_0"
        assert rubric["criteria"][1]["id"] == "criterion_1"
        assert rubric["criteria"][2]["id"] == "criterion_2"

    def test_element_with_aliases_still_expands(self):
        """Single element with aliases still expands for granularity."""
        card = self._make_card(elements=[{"text": "最花時間的步驟", "aliases": ["瓶頸", "耗時"]}])
        rubric = self.service.compile_rubric_from_elements(card)

        assert len(rubric["criteria"]) >= 2

    def test_empty_elements_and_anchors_returns_minimal(self):
        card = self._make_card(elements=[], anchors=[])
        rubric = self.service.compile_rubric_from_elements(card)

        assert rubric["rubricVersion"] == "v1"
        assert rubric["criteria"] == []


class TestGetOrCompileRubric:
    """Test the main entry point with caching."""

    def setup_method(self):
        self.service = QuestionRubricService()

    def test_returns_existing_rubric(self):
        card = Mock(spec=QuestionCard)
        card.id = "card-1"
        card.coverage_rule = {
            "rubricVersion": "v1",
            "answerTarget": "existing target",
            "criteria": [{"id": "c0", "description": "test"}],
        }
        db = Mock()

        rubric = self.service.get_or_compile_rubric(db, card)

        assert rubric["answerTarget"] == "existing target"
        assert rubric["criteria"][0]["id"] == "c0"

    def test_compiles_from_elements_when_no_rubric(self):
        card = Mock(spec=QuestionCard)
        card.id = "card-2"
        card.question_text = "問題"
        card.focus_text = "重點"
        card.question_type = "value_slot"
        card.coverage_rule = {
            "mustMentionElements": [{"text": "步驟"}],
            "semanticAnchors": [],
        }
        db = Mock()

        rubric = self.service.get_or_compile_rubric(db, card)

        assert rubric["rubricVersion"] == "v1"
        assert len(rubric["criteria"]) >= 2  # Single element expands
        db.flush.assert_called()

    @patch("app.services.question_rubric_service.openai_service")
    def test_generates_with_llm_when_no_elements(self, mock_openai):
        card = Mock(spec=QuestionCard)
        card.id = "card-3"
        card.question_text = "專案目前最大的挑戰是什麼？"
        card.focus_text = "挑戰"
        card.question_type = "open"
        card.coverage_rule = {}
        db = Mock()

        mock_openai.chat_completion.return_value = {
            "answerTarget": "找出專案挑戰",
            "criteria": [
                {
                    "id": "criterion_0",
                    "description": "主要挑戰",
                    "type": "value_slot",
                    "required": True,
                    "critical": True,
                    "weight": 1.0,
                }
            ],
        }

        rubric = self.service.get_or_compile_rubric(db, card)

        assert rubric["rubricVersion"] == "v1"
        assert len(rubric["criteria"]) >= 1
        mock_openai.chat_completion.assert_called_once()


class TestRubricStability:
    """Test that rubrics don't drift across evaluations."""

    def setup_method(self):
        self.service = QuestionRubricService()

    def test_same_card_returns_same_rubric(self):
        card = Mock(spec=QuestionCard)
        card.id = "card-stable"
        card.question_text = "問題"
        card.focus_text = "重點"
        card.question_type = "value_slot"
        card.coverage_rule = {
            "mustMentionElements": [{"text": "A"}, {"text": "B"}],
            "semanticAnchors": [],
        }

        rubric1 = self.service.compile_rubric_from_elements(card)
        rubric2 = self.service.compile_rubric_from_elements(card)

        assert rubric1 == rubric2

    def test_once_compiled_returns_cached(self):
        card = Mock(spec=QuestionCard)
        card.id = "card-cache"
        card.coverage_rule = {
            "rubricVersion": "v1",
            "answerTarget": "cached",
            "criteria": [{"id": "c0", "description": "cached criterion"}],
            "mustMentionElements": [{"text": "should not recompile"}],
        }
        db = Mock()

        rubric = self.service.get_or_compile_rubric(db, card)

        # Should use cached version, not recompile from elements
        assert rubric["answerTarget"] == "cached"
        assert rubric["criteria"][0]["description"] == "cached criterion"
