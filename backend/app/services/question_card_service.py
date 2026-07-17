"""Question Card service for managing question card operations."""

import logging
import re
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.question_card import QuestionCard
from app.schemas.question_card import CoverageRule, QuestionCardCreate, QuestionCardUpdate

logger = logging.getLogger(__name__)


class QuestionCardService:
    """Service for question card operations."""

    MAX_IMPORTANT_ELEMENTS = 3

    @classmethod
    def _element_text(cls, element: Any) -> str:
        if isinstance(element, dict):
            return str(element.get("text", "") or "").strip()
        return str(element or "").strip()

    @staticmethod
    def _clean_numbered_point(text: str) -> str:
        return re.sub(
            r"^\s*(?:\d+(?:[-.．、]\d+)*|[一二三四五六七八九十]+)[).．、:\-：]?\s*",
            "",
            str(text or "").strip(),
        ).strip()

    def normalize_coverage_rule_for_important_elements(
        self, coverage_rule: Dict[str, Any] | None
    ) -> Dict[str, Any]:
        """
        Keep semantic anchors as matching hints, but make important elements the
        canonical visible/scoring units.

        Answer elements represent the key information expected in the response.
        """
        if hasattr(coverage_rule, "model_dump"):
            coverage_rule = coverage_rule.model_dump()
        rule = deepcopy(coverage_rule or {})
        semantic_anchors = [
            str(anchor).strip()
            for anchor in (rule.get("semanticAnchors") or [])
            if str(anchor or "").strip()
        ]

        raw_elements: List[Dict[str, Any]] = []
        for element in rule.get("mustMentionElements") or []:
            text = self._element_text(element)
            if not text:
                continue
            if isinstance(element, dict):
                raw_elements.append(
                    {
                        "text": self._clean_numbered_point(text),
                        "required": bool(element.get("required", True)),
                        "aliases": (
                            element.get("aliases")
                            if isinstance(element.get("aliases"), list)
                            else []
                        ),
                        "subpoints": (
                            [
                                self._clean_numbered_point(subpoint)
                                for subpoint in element.get("subpoints", [])
                                if self._clean_numbered_point(subpoint)
                            ]
                            if isinstance(element.get("subpoints"), list)
                            else []
                        ),
                    }
                )
            else:
                raw_elements.append(
                    {
                        "text": self._clean_numbered_point(text),
                        "required": True,
                        "aliases": [],
                        "subpoints": [],
                    }
                )

        # Keep only the most important elements (limit to MAX_IMPORTANT_ELEMENTS)
        normalized_elements = raw_elements[: self.MAX_IMPORTANT_ELEMENTS]

        rule["semanticAnchors"] = semantic_anchors
        rule["mustMentionElements"] = normalized_elements
        rule["expectedKeywords"] = rule.get("expectedKeywords") or []
        rule["negativeSignals"] = rule.get("negativeSignals") or []
        rule.setdefault("thresholds", {"probablySufficient": 0.62, "sufficient": 0.78})
        rule.setdefault(
            "scoringWeights",
            {"semanticSimilarity": 0.55, "keywordCoverage": 0.25, "elementCoverage": 0.20},
        )

        return rule

    def get_question_card(self, db: Session, card_id: str) -> QuestionCard:
        """Get a question card by ID."""
        card = db.query(QuestionCard).filter(QuestionCard.id == card_id).first()
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Question card {card_id} not found"
            )
        return card

    def get_question_cards_by_document(self, db: Session, document_id: str) -> List[QuestionCard]:
        """Get all question cards for a document, ordered by theme and order index."""
        return (
            db.query(QuestionCard)
            .filter(QuestionCard.document_id == document_id)
            .order_by(QuestionCard.interview_theme_id, QuestionCard.order_index)
            .all()
        )

    def create_question_card(
        self,
        db: Session,
        document_id: str,
        card_data: QuestionCardCreate,
        created_by: str = "user",
        interview_theme_id: str = "",
    ) -> QuestionCard:
        """Create a new question card."""
        card_id = f"qcard_{uuid.uuid4().hex[:12]}"

        if not interview_theme_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="themeId is required"
            )

        # Get next order index for this theme
        max_order = (
            db.query(func.max(QuestionCard.order_index))
            .filter(QuestionCard.interview_theme_id == interview_theme_id)
            .scalar()
            or -1
        )
        order_index = max_order + 1

        # Resolve fields (supports both frontend and internal naming)
        question_text = (
            getattr(card_data, "resolved_question_text", None)
            or card_data.questionText
            or card_data.title
            or "Untitled"
        )
        question_type = (
            getattr(card_data, "resolved_question_type", None)
            or card_data.questionType
            or "clarification"
        )
        suggested_followup = (
            getattr(card_data, "resolved_followup", None)
            or card_data.suggestedFollowup
            or card_data.suggestedScript
            or ""
        )

        # If AI needs to generate coverage rule
        coverage_rule = card_data.coverageRule
        if not coverage_rule:
            coverage_rule = {
                "semanticAnchors": [question_text],
                "expectedKeywords": [],
                "mustMentionElements": [],
                "negativeSignals": [],
                "thresholds": {"probablySufficient": 0.62, "sufficient": 0.78},
                "scoringWeights": {
                    "semanticSimilarity": 0.55,
                    "keywordCoverage": 0.25,
                    "elementCoverage": 0.20,
                },
            }

        # Normalize coverage rule
        coverage_rule = self.normalize_coverage_rule_for_important_elements(coverage_rule)

        # Create question card
        card = QuestionCard(
            id=card_id,
            document_id=document_id,
            interview_theme_id=interview_theme_id,
            question_text=question_text,
            question_type=question_type,
            importance=card_data.importance,
            coverage_rule=coverage_rule,
            suggested_followup=suggested_followup,
            expected_answer_elements=card_data.expectedAnswerElements or [],
            estimated_seconds=card_data.estimatedSeconds or 30,
            order_index=order_index,
            status="pending",
            confidence=None,
            ui={"color": "default", "isVisible": True, "isPinned": False, "displayMode": "full"},
            created_by=created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(card)
        db.commit()
        db.refresh(card)

        logger.info(f"Created question card {card_id}")
        return card

    def _auto_generate_criteria(self, db: Session, card: QuestionCard) -> None:
        """Generate criteria via LLM and save to card after creation."""
        from app.services.question_rubric_service import question_rubric_service

        try:
            rubric = question_rubric_service.generate_rubric_with_llm(card)
            criteria = rubric.get("criteria")
            if criteria:
                coverage_rule = dict(card.coverage_rule or {})
                coverage_rule["criteria"] = criteria
                coverage_rule["rubricVersion"] = rubric.get("rubricVersion", "v1")
                coverage_rule["answerTarget"] = rubric.get("answerTarget", "")
                card.coverage_rule = coverage_rule
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(card, "coverage_rule")
                db.commit()
                db.refresh(card)
                logger.info(f"Auto-generated {len(criteria)} criteria for card {card.id}")
        except Exception as e:
            logger.warning(f"Failed to auto-generate criteria for card {card.id}: {e}")

    _FIELD_MAP = {
        "questionText": "question_text",
        "suggestedFollowup": "suggested_followup",
        "questionType": "question_type",
        "coverageRule": "coverage_rule",
        "expectedAnswerElements": "expected_answer_elements",
        "estimatedSeconds": "estimated_seconds",
        "orderIndex": "order_index",
    }

    def update_question_card(
        self, db: Session, card_id: str, card_update: QuestionCardUpdate
    ) -> QuestionCard:
        """Update a question card."""
        card = self.get_question_card(db, card_id)

        update_data = card_update.model_dump(exclude_unset=True)
        question_text_changed = False
        criteria_explicitly_provided = False

        for field, value in update_data.items():
            model_field = self._FIELD_MAP.get(field, field)
            if model_field == "coverage_rule" and value:
                if value.get("criteria"):
                    criteria_explicitly_provided = True
                value = self.normalize_coverage_rule_for_important_elements(value)
            if model_field == "question_text" and value != card.question_text:
                question_text_changed = True
            setattr(card, model_field, value)

        card.updated_at = datetime.utcnow()

        if question_text_changed and not criteria_explicitly_provided:
            self._regenerate_rubric(db, card)
        elif not criteria_explicitly_provided and not (card.coverage_rule or {}).get("criteria"):
            self._auto_generate_criteria(db, card)

        db.commit()
        db.refresh(card)

        logger.info(f"Updated question card {card_id}")
        return card

    def _regenerate_rubric(self, db: Session, card: QuestionCard) -> None:
        """Clear stale rubric and regenerate criteria after question_text change."""
        coverage_rule = dict(card.coverage_rule or {})
        coverage_rule.pop("rubricVersion", None)
        coverage_rule.pop("answerTarget", None)
        coverage_rule.pop("criteria", None)
        coverage_rule["semanticAnchors"] = [card.question_text]
        card.coverage_rule = coverage_rule
        db.flush()

        self._auto_generate_criteria(db, card)

    def delete_question_card(self, db: Session, card_id: str) -> None:
        """Delete a question card."""
        card = self.get_question_card(db, card_id)
        db.delete(card)
        db.commit()
        logger.info(f"Deleted question card {card_id}")

    def reorder_question_cards(self, db: Session, card_ids: List[str]) -> List[QuestionCard]:
        """Reorder question cards by their IDs."""
        cards = []
        for index, card_id in enumerate(card_ids):
            card = self.get_question_card(db, card_id)
            card.order_index = index
            card.updated_at = datetime.utcnow()
            cards.append(card)

        db.commit()
        for card in cards:
            db.refresh(card)

        logger.info(f"Reordered {len(cards)} question cards")
        return cards


# Singleton instance
question_card_service = QuestionCardService()
