"""Question Rubric Service for compiling evaluation criteria from question cards."""

import json
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.question_card import QuestionCard
from app.services.openai_service import openai_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class QuestionRubricService:
    """Service for compiling and managing question evaluation rubrics."""

    def get_or_compile_rubric(self, db: Session, card: QuestionCard) -> Dict[str, Any]:
        """
        Get existing rubric from coverage_rule, or compile one from existing data.

        Args:
            db: Database session
            card: QuestionCard instance

        Returns:
            Rubric dictionary with rubricVersion, answerTarget, and criteria
        """
        # Check if coverage_rule already has a rubric
        coverage_rule = card.coverage_rule or {}

        if coverage_rule.get("rubricVersion") and coverage_rule.get("criteria"):
            logger.info(f"Found existing rubric for card {card.id}")
            return {
                "rubricVersion": coverage_rule["rubricVersion"],
                "answerTarget": coverage_rule.get("answerTarget", ""),
                "criteria": coverage_rule["criteria"]
            }

        # Check if card has mustMentionElements to convert
        must_mention_elements = coverage_rule.get("mustMentionElements") or []
        semantic_anchors = coverage_rule.get("semanticAnchors") or []

        if must_mention_elements or semantic_anchors:
            logger.info(f"Compiling rubric from existing elements for card {card.id}")
            rubric = self.compile_rubric_from_elements(card)
        else:
            logger.info(f"Generating rubric with LLM for card {card.id}")
            rubric = self.generate_rubric_with_llm(card)

        # Cache the rubric back into coverage_rule
        self._save_rubric_to_card(db, card, rubric)

        return rubric

    def compile_rubric_from_elements(self, card: QuestionCard) -> Dict[str, Any]:
        """
        Convert mustMentionElements/semanticAnchors into criteria format.

        Args:
            card: QuestionCard instance

        Returns:
            Rubric dictionary with criteria derived from existing elements
        """
        coverage_rule = card.coverage_rule or {}
        must_mention_elements = coverage_rule.get("mustMentionElements") or []
        semantic_anchors = coverage_rule.get("semanticAnchors") or []

        criteria = []

        # Convert each mustMentionElement into a criterion
        if must_mention_elements:
            for idx, element in enumerate(must_mention_elements):
                if isinstance(element, dict):
                    text = element.get("text", "")
                    required = element.get("required", True)
                else:
                    text = str(element)
                    required = True

                if not text:
                    continue

                # Determine if this is critical (first one is critical if multiple exist)
                is_critical = (idx == 0) if len(must_mention_elements) > 1 else True

                # Calculate weight (distribute equally)
                weight = 1.0 / len(must_mention_elements) if len(must_mention_elements) > 0 else 1.0

                criterion = {
                    "id": f"criterion_{idx}",
                    "description": text,
                    "type": "value_slot",
                    "required": required,
                    "critical": is_critical,
                    "weight": round(weight, 2)
                }
                criteria.append(criterion)

        # If no mustMentionElements, use semanticAnchors
        elif semantic_anchors:
            for idx, anchor in enumerate(semantic_anchors):
                if not anchor:
                    continue

                is_critical = (idx == 0) if len(semantic_anchors) > 1 else True
                weight = 1.0 / len(semantic_anchors) if len(semantic_anchors) > 0 else 1.0

                criterion = {
                    "id": f"criterion_{idx}",
                    "description": anchor,
                    "type": "value_slot",
                    "required": True,
                    "critical": is_critical,
                    "weight": round(weight, 2)
                }
                criteria.append(criterion)

        # Derive answer target from question text
        answer_target = self._derive_answer_target(card.question_text)

        return {
            "rubricVersion": "v1",
            "answerTarget": answer_target,
            "criteria": criteria
        }

    def generate_rubric_with_llm(self, card: QuestionCard) -> Dict[str, Any]:
        """
        Use LLM to generate criteria when no elements exist.

        Args:
            card: QuestionCard instance

        Returns:
            Generated rubric with AI-created criteria
        """
        # Build prompt for rubric generation
        system_prompt = """你是評分標準設計專家。根據訪談問題，設計 2-4 個評分準則（criteria）。

每個準則應該：
- 描述完整回答必須包含的資訊類型
- 明確、可驗證
- 使用繁體中文

輸出格式（JSON）：
{
  "rubricVersion": "v1",
  "answerTarget": "這個問題期待的答案內容摘要",
  "criteria": [
    {
      "id": "criterion_0",
      "description": "評分準則描述",
      "type": "value_slot",
      "required": true,
      "critical": true,
      "weight": 0.5
    }
  ]
}

規則：
- 產生 2-4 個準則
- 第一個準則設為 critical: true
- weight 總和應為 1.0
- type 固定為 "value_slot"
- description 要具體明確
"""

        user_prompt = f"""問題文字：{card.question_text}

問題類型：{card.question_type}

重點焦點：{card.focus_text or '(無)'}

請產生這個問題的評分準則（criteria）。以 JSON 格式回傳。
"""

        try:
            response = openai_service.client.chat.completions.create(
                model=settings.SEMANTIC_UNDERSTANDING_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from OpenAI")

            rubric = json.loads(content)
            logger.info(f"Generated rubric with {len(rubric.get('criteria', []))} criteria for card {card.id}")

            # Validate and normalize the response
            if not rubric.get("criteria"):
                raise ValueError("No criteria generated")

            # Ensure rubric has required fields
            rubric.setdefault("rubricVersion", "v1")
            rubric.setdefault("answerTarget", self._derive_answer_target(card.question_text))

            return rubric

        except Exception as e:
            logger.error(f"Failed to generate rubric with LLM for card {card.id}: {e}")
            # Fallback to basic rubric
            return self._create_fallback_rubric(card)

    def _derive_answer_target(self, question_text: str) -> str:
        """
        Derive a concise answer target from question text.

        Args:
            question_text: The question text

        Returns:
            Concise description of expected answer
        """
        # Simple heuristic: extract key phrases or return shortened version
        if len(question_text) <= 50:
            return question_text

        # Try to find key action verbs and objects
        import re

        # Common question patterns in Chinese
        patterns = [
            r'請.*?說明(.{5,30})',
            r'請.*?描述(.{5,30})',
            r'請.*?確認(.{5,30})',
            r'如何(.{5,30})',
            r'什麼(.{5,30})',
            r'哪些(.{5,30})',
        ]

        for pattern in patterns:
            match = re.search(pattern, question_text)
            if match:
                return match.group(1).strip('，。、；：')

        # Fallback: return first 40 characters
        return question_text[:40] + "..." if len(question_text) > 40 else question_text

    def _create_fallback_rubric(self, card: QuestionCard) -> Dict[str, Any]:
        """
        Create a basic fallback rubric when LLM generation fails.

        Args:
            card: QuestionCard instance

        Returns:
            Basic rubric with single criterion
        """
        return {
            "rubricVersion": "v1",
            "answerTarget": self._derive_answer_target(card.question_text),
            "criteria": [
                {
                    "id": "criterion_0",
                    "description": "提供完整且清楚的回答",
                    "type": "value_slot",
                    "required": True,
                    "critical": True,
                    "weight": 1.0
                }
            ]
        }

    def _save_rubric_to_card(self, db: Session, card: QuestionCard, rubric: Dict[str, Any]) -> None:
        """
        Save the compiled rubric back to the card's coverage_rule.
        Maintains backward compatibility by not removing existing fields.

        Args:
            db: Database session
            card: QuestionCard instance
            rubric: Rubric dictionary to save
        """
        try:
            # Get existing coverage_rule or create new one
            coverage_rule = card.coverage_rule or {}

            # Add rubric fields alongside existing fields
            coverage_rule["rubricVersion"] = rubric["rubricVersion"]
            coverage_rule["answerTarget"] = rubric["answerTarget"]
            coverage_rule["criteria"] = rubric["criteria"]

            # Update the card (flush only — let caller commit)
            card.coverage_rule = coverage_rule

            db.flush()

            logger.info(f"Saved rubric to card {card.id}")

        except Exception as e:
            logger.error(f"Failed to save rubric to card {card.id}: {e}")
            db.rollback()
            raise


    def pre_warm_rubrics(self, db: Session, cards: List[QuestionCard]) -> None:
        """Pre-compile rubrics for all cards that don't have one yet.

        Call this when a session starts to avoid latency during first utterance evaluation.
        """
        for card in cards:
            coverage_rule = card.coverage_rule or {}
            if coverage_rule.get("rubricVersion") and coverage_rule.get("criteria"):
                continue
            try:
                self.get_or_compile_rubric(db, card)
            except Exception as e:
                logger.warning(f"Failed to pre-warm rubric for card {card.id}: {e}")
        db.commit()


# Singleton instance
question_rubric_service = QuestionRubricService()
