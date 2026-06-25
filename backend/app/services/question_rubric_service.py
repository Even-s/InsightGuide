"""Question Rubric Service for compiling evaluation criteria from question cards."""

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.question_card import QuestionCard
from app.services.openai_service import openai_service

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
                "criteria": coverage_rule["criteria"],
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

    # Question-type patterns for local criterion expansion
    _SITUATION_PATTERNS = ("情境", "場景", "情況", "案例", "例子", "scenario")
    _PROCESS_PATTERNS = ("流程", "步驟", "做法", "方式", "怎麼做", "process")
    _REASON_PATTERNS = ("為什麼", "原因", "動機", "理由", "why")
    _FREQUENCY_PATTERNS = ("多常", "頻率", "多久", "幾次", "多少次")

    def _expand_single_element(self, element_text: str, card: QuestionCard) -> List[Dict[str, Any]]:
        """Expand a single broad element into 2-3 concrete criteria based on question type."""
        question_text = (card.question_text or "").lower()
        focus_text = (card.focus_text or "").lower()
        combined = question_text + focus_text + element_text.lower()

        # Detect question pattern and generate appropriate sub-criteria
        if any(p in combined for p in self._SITUATION_PATTERNS):
            return [
                {
                    "id": "criterion_0",
                    "description": f"提到至少一個具體的{element_text}",
                    "type": "value_slot",
                    "required": True,
                    "critical": True,
                    "weight": 0.5,
                },
                {
                    "id": "criterion_1",
                    "description": "說明為什麼需要幫忙或問題發生的原因",
                    "type": "value_slot",
                    "required": True,
                    "critical": False,
                    "weight": 0.3,
                },
                {
                    "id": "criterion_2",
                    "description": "提及頻率、影響程度或具體例子細節",
                    "type": "value_slot",
                    "required": False,
                    "critical": False,
                    "weight": 0.2,
                },
            ]

        if any(p in combined for p in self._PROCESS_PATTERNS):
            return [
                {
                    "id": "criterion_0",
                    "description": f"描述{element_text}的具體步驟或做法",
                    "type": "value_slot",
                    "required": True,
                    "critical": True,
                    "weight": 0.5,
                },
                {
                    "id": "criterion_1",
                    "description": "說明誰參與或負責哪個環節",
                    "type": "value_slot",
                    "required": True,
                    "critical": False,
                    "weight": 0.3,
                },
                {
                    "id": "criterion_2",
                    "description": "提及遇到的困難或目前的限制",
                    "type": "value_slot",
                    "required": False,
                    "critical": False,
                    "weight": 0.2,
                },
            ]

        if any(p in combined for p in self._REASON_PATTERNS):
            return [
                {
                    "id": "criterion_0",
                    "description": f"說明{element_text}的具體原因",
                    "type": "value_slot",
                    "required": True,
                    "critical": True,
                    "weight": 0.5,
                },
                {
                    "id": "criterion_1",
                    "description": "提供支持原因的具體事實或例子",
                    "type": "value_slot",
                    "required": True,
                    "critical": False,
                    "weight": 0.3,
                },
                {
                    "id": "criterion_2",
                    "description": "描述影響或後果",
                    "type": "value_slot",
                    "required": False,
                    "critical": False,
                    "weight": 0.2,
                },
            ]

        # Default expansion: core fact + supporting detail
        return [
            {
                "id": "criterion_0",
                "description": f"提到{element_text}的具體內容或例子",
                "type": "value_slot",
                "required": True,
                "critical": True,
                "weight": 0.6,
            },
            {
                "id": "criterion_1",
                "description": "補充說明原因、影響或相關細節",
                "type": "value_slot",
                "required": True,
                "critical": False,
                "weight": 0.4,
            },
        ]

    def compile_rubric_from_elements(self, card: QuestionCard) -> Dict[str, Any]:
        """
        Convert mustMentionElements/semanticAnchors into criteria format.
        When only one element exists, expands it into 2-3 concrete criteria
        for better scoring granularity.
        """
        coverage_rule = card.coverage_rule or {}
        must_mention_elements = (
            coverage_rule.get("mustMentionElements")
            or coverage_rule.get("must_mention_elements")
            or []
        )
        semantic_anchors = (
            coverage_rule.get("semanticAnchors") or coverage_rule.get("semantic_anchors") or []
        )

        criteria = []

        if must_mention_elements:
            # Filter valid elements
            valid_elements = []
            for element in must_mention_elements:
                if isinstance(element, dict):
                    text = element.get("text", "")
                else:
                    text = str(element)
                if text:
                    valid_elements.append((text, element))

            if len(valid_elements) == 1:
                # Single element: expand into 2-3 sub-criteria for granularity
                text, _ = valid_elements[0]
                criteria = self._expand_single_element(text, card)
            else:
                # Multiple elements: use them directly as criteria
                for idx, (text, element) in enumerate(valid_elements):
                    required = element.get("required", True) if isinstance(element, dict) else True
                    is_critical = idx == 0
                    weight = round(1.0 / len(valid_elements), 2)
                    criteria.append(
                        {
                            "id": f"criterion_{idx}",
                            "description": text,
                            "type": "value_slot",
                            "required": required,
                            "critical": is_critical,
                            "weight": weight,
                        }
                    )

        elif semantic_anchors:
            valid_anchors = [a for a in semantic_anchors if a]

            if len(valid_anchors) == 1:
                criteria = self._expand_single_element(valid_anchors[0], card)
            else:
                for idx, anchor in enumerate(valid_anchors):
                    is_critical = idx == 0
                    weight = round(1.0 / len(valid_anchors), 2)
                    criteria.append(
                        {
                            "id": f"criterion_{idx}",
                            "description": anchor,
                            "type": "value_slot",
                            "required": True,
                            "critical": is_critical,
                            "weight": weight,
                        }
                    )

        answer_target = self._derive_answer_target(card.question_text)

        return {
            "rubricVersion": "v1",
            "answerTarget": answer_target,
            "criteria": criteria,
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
        system_prompt = """你是訪談回答評分標準設計專家。根據訪談問題，設計具體、可觀察的評分準則。

核心原則：
- 每個準則描述「受訪者的回答中必須包含什麼具體資訊」
- 準則必須是可從回答中觀察到的事實，不是抽象感受
- 禁止使用「提供完整且清楚的回答」這類泛用描述
- 每個準則要能獨立判斷：看到特定資訊就算滿足，看不到就不算

好的準則範例：
- 「提到至少一個具體的情境或場景名稱」
- 「描述遇到的具體困難或卡住的原因」
- 「說明目前的處理方式或應對做法」
- 「提及相關的人員角色（誰參與）」
- 「提供頻率、時間或數量等量化資訊」

壞的準則（禁止使用）：
- 「提供完整且清楚的回答」（太泛，無法判斷）
- 「回答有深度」（主觀）
- 「涵蓋所有面向」（無邊界）

輸出格式（JSON）：
{
  "rubricVersion": "v1",
  "answerTarget": "這個問題期待的答案摘要（一句話）",
  "criteria": [
    {
      "id": "criterion_0",
      "description": "具體可觀察的評分準則",
      "type": "value_slot",
      "required": true,
      "critical": true,
      "weight": 0.4
    }
  ]
}

規則：
- 必須產生 2-4 個準則（不得只有 1 個）
- 第一個準則設為 critical: true（核心資訊）
- weight 總和必須為 1.0
- type 固定為 "value_slot"
- description 必須具體、可觀察、不含「完整」「清楚」等泛詞
- 準則要能區分「只是提到主題」vs「真正回答了問題」
"""

        user_prompt = f"""問題文字：{card.question_text}

問題類型：{card.question_type}

重點焦點：{card.focus_text or '(無)'}

請為這個訪談問題設計 2-4 個具體的評分準則。
每個準則要描述「回答中必須看到什麼具體資訊才算滿足」。
以 JSON 格式回傳。
"""

        try:
            rubric = openai_service.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=settings.SEMANTIC_UNDERSTANDING_MODEL,
                temperature=0.3,
                response_format={"type": "json_object"},
                purpose="rubric_generation",
            )

            if not rubric or not isinstance(rubric, dict):
                raise ValueError("Empty or invalid response from OpenAI")

            logger.info(
                f"Generated rubric with {len(rubric.get('criteria', []))} criteria for card {card.id}"
            )

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
            r"請.*?說明(.{5,30})",
            r"請.*?描述(.{5,30})",
            r"請.*?確認(.{5,30})",
            r"如何(.{5,30})",
            r"什麼(.{5,30})",
            r"哪些(.{5,30})",
        ]

        for pattern in patterns:
            match = re.search(pattern, question_text)
            if match:
                return match.group(1).strip("，。、；：")

        # Fallback: return first 40 characters
        return question_text[:40] + "..." if len(question_text) > 40 else question_text

    def _create_fallback_rubric(self, card: QuestionCard) -> Dict[str, Any]:
        """
        Create a basic fallback rubric when LLM generation fails.
        Uses two criteria for better granularity than a single generic one.
        """
        answer_target = self._derive_answer_target(card.question_text)
        return {
            "rubricVersion": "v1",
            "answerTarget": answer_target,
            "criteria": [
                {
                    "id": "criterion_0",
                    "description": f"提到至少一個具體的情境、例子或場景",
                    "type": "value_slot",
                    "required": True,
                    "critical": True,
                    "weight": 0.6,
                },
                {
                    "id": "criterion_1",
                    "description": f"描述具體的做法、原因或影響",
                    "type": "value_slot",
                    "required": True,
                    "critical": False,
                    "weight": 0.4,
                },
            ],
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

    def get_rubric_if_cached(self, card: QuestionCard) -> Optional[Dict[str, Any]]:
        """Return rubric without LLM. Uses compiled cache, or compiles locally from elements."""
        coverage_rule = card.coverage_rule or {}
        if coverage_rule.get("rubricVersion") and coverage_rule.get("criteria"):
            return {
                "rubricVersion": coverage_rule["rubricVersion"],
                "answerTarget": coverage_rule.get("answerTarget", ""),
                "criteria": coverage_rule["criteria"],
            }

        # Can compile locally from elements (no LLM needed)
        # Check both camelCase and snake_case keys
        must_mention = (
            coverage_rule.get("mustMentionElements")
            or coverage_rule.get("must_mention_elements")
            or []
        )
        semantic_anchors = (
            coverage_rule.get("semanticAnchors") or coverage_rule.get("semantic_anchors") or []
        )
        if must_mention or semantic_anchors:
            return self.compile_rubric_from_elements(card)

        return None

    def compile_and_save_rubric(self, db: Session, card: QuestionCard) -> None:
        """Compile rubric immediately after card creation (local, no LLM).

        No-op if rubric already exists. Safe to call on any card.
        """
        coverage_rule = card.coverage_rule or {}
        if coverage_rule.get("rubricVersion") and coverage_rule.get("criteria"):
            return

        must_mention = (
            coverage_rule.get("mustMentionElements")
            or coverage_rule.get("must_mention_elements")
            or []
        )
        semantic_anchors = (
            coverage_rule.get("semanticAnchors") or coverage_rule.get("semantic_anchors") or []
        )

        if must_mention or semantic_anchors:
            rubric = self.compile_rubric_from_elements(card)
            self._save_rubric_to_card(db, card, rubric)

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
