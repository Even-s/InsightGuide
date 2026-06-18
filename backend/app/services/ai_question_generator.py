"""AI service for generating and regenerating question card fields."""

import logging
from typing import Dict, Any, Optional, List
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)


class AIQuestionGenerator:
    """Generate question card metadata and followup questions."""

    def regenerate_suggested_followup(
        self,
        question_text: str,
        expected_answer_elements: List[str],
        section_context: str = "",
        current_followup: str = "",
    ) -> str:
        """
        Regenerate only the suggested followup question.

        Args:
            question_text: The main interview question
            expected_answer_elements: Expected elements in a sufficient answer
            section_context: Context from the document section
            current_followup: Current followup question (to avoid duplication)

        Returns:
            Regenerated followup question
        """
        try:
            prompt = self._build_followup_regeneration_prompt(
                question_text=question_text,
                expected_answer_elements=expected_answer_elements,
                section_context=section_context,
                current_followup=current_followup,
            )

            response = openai_service.generate_card_metadata(prompt)
            suggested_followup = str(response.get("suggestedFollowup", "")).strip()

            if not suggested_followup:
                raise ValueError("Empty suggestedFollowup from AI")

            if self._normalize_text(suggested_followup) == self._normalize_text(current_followup):
                raise ValueError("AI returned the same followup question")

            return suggested_followup[:500]  # Limit followup length

        except Exception as e:
            logger.error(f"Failed to regenerate followup question: {e}")
            raise

    def generate_question_fields(
        self,
        question_text: str,
        section_context: str = "",
        document_context: str = ""
    ) -> Dict[str, Any]:
        """
        Generate all question card fields from the question text.

        Args:
            question_text: The interview question
            section_context: Context from the document section
            document_context: Broader document context

        Returns:
            Dictionary containing generated fields:
            - question_type: Type of question (clarification, validation, etc.)
            - importance: must or should
            - expected_answer_elements: Key points that should be covered
            - coverage_rule: Rules for evaluating answer sufficiency
            - suggested_followup: Followup question if answer is insufficient
        """
        try:
            prompt = self._build_generation_prompt(
                question_text,
                section_context,
                document_context
            )
            response = openai_service.generate_card_metadata(prompt)

            return self._parse_response(response, question_text)

        except Exception as e:
            logger.error(f"Failed to generate question fields: {e}")
            # Return sensible defaults if AI generation fails
            return self._generate_fallback_fields(question_text)

    def _build_followup_regeneration_prompt(
        self,
        question_text: str,
        expected_answer_elements: List[str],
        section_context: str,
        current_followup: str,
    ) -> str:
        """Build prompt for regenerating a followup question."""
        elements_text = "\n".join(f"- {elem}" for elem in expected_answer_elements)

        return f"""請為以下訪談問題重新生成一個追問問題。

主要問題：{question_text}

期望回答要素：
{elements_text}

情境說明：
{section_context or "需求訪談"}

目前的追問（請生成不同的版本）：
{current_followup}

要求：
1. 追問應該針對可能不充分的回答
2. 幫助受訪者提供更具體、更完整的資訊
3. 與主要問題相關但角度不同
4. 用開放式問句，鼓勵詳細回答
5. 長度控制在 50 字以內

請以 JSON 格式回應：
{{
  "suggestedFollowup": "你的追問問題"
}}"""

    def _build_generation_prompt(
        self,
        question_text: str,
        section_context: str,
        document_context: str
    ) -> str:
        """Build prompt for generating question metadata."""
        return f"""請分析以下訪談問題，並生成相關的元資料。

問題：{question_text}

段落情境：
{section_context or "需求文件段落"}

文件情境：
{document_context or "需求文件"}

請生成：
1. 問題類型（clarification, validation, exploration, edge_case, constraint, priority）
2. 重要性（must: 關鍵需求必問, should: 重要但非關鍵）
3. 期望回答要素（一個充分的回答應該包含哪些關鍵點）
4. 語意錨點（用於評估回答充分度的關鍵詞）
5. 建議追問（如果回答不充分時的追問）

請以 JSON 格式回應：
{{
  "questionType": "clarification|validation|exploration|edge_case|constraint|priority",
  "importance": "must|should",
  "expectedAnswerElements": ["要素1", "要素2", "..."],
  "suggestedFollowup": "追問問題",
  "coverageRule": {{
    "semanticAnchors": ["語意錨點1", "錨點2"],
    "expectedKeywords": ["關鍵字1", "關鍵字2"],
    "mustMentionElements": [
      {{"text": "必須提到的要素", "required": true, "aliases": [], "subpoints": []}}
    ],
    "thresholds": {{
      "probablySufficient": 0.65,
      "sufficient": 0.80
    }}
  }}
}}"""

    def _parse_response(
        self,
        response: Dict[str, Any],
        question_text: str
    ) -> Dict[str, Any]:
        """Parse AI response into question card fields."""
        return {
            "question_type": response.get("questionType", "clarification"),
            "importance": response.get("importance", "should"),
            "expected_answer_elements": response.get("expectedAnswerElements", []),
            "suggested_followup": response.get("suggestedFollowup", ""),
            "coverage_rule": response.get("coverageRule", self._generate_default_coverage_rule(question_text)),
        }

    def _generate_fallback_fields(self, question_text: str) -> Dict[str, Any]:
        """Generate fallback fields if AI generation fails."""
        return {
            "question_type": "clarification",
            "importance": "should",
            "expected_answer_elements": [],
            "suggested_followup": "可以請您詳細說明嗎？",
            "coverage_rule": self._generate_default_coverage_rule(question_text),
        }

    def _generate_default_coverage_rule(self, question_text: str) -> Dict[str, Any]:
        """Generate a basic coverage rule from question text."""
        # Extract keywords from question (simple approach)
        keywords = [word for word in question_text.split() if len(word) > 2][:5]

        return {
            "semantic_anchors": keywords,
            "expected_keywords": [],
            "must_mention_elements": [],
            "thresholds": {
                "probably_sufficient": 0.65,
                "sufficient": 0.80
            },
            "scoring_weights": {
                "semantic_similarity": 0.60,
                "keyword_coverage": 0.20,
                "element_coverage": 0.20
            }
        }

    def generate_role_targeting(
        self,
        question_text: str,
        question_type: str = "",
        section_context: str = "",
    ) -> Dict[str, Any]:
        """Generate role targeting metadata for a question card.

        Returns:
            {
                "target_roles": ["engineering", "IT"],
                "not_recommended_roles": ["sales"],
                "expertise_required": ["system_architecture", "API"],
                "question_intent": "technical_constraint"
            }
        """
        try:
            prompt = (
                "分析以下訪談問題，判斷這題適合問哪些角色的人。\n\n"
                f"問題：{question_text}\n"
                f"問題類型：{question_type or '未指定'}\n"
                f"情境：{section_context or '需求訪談'}\n\n"
                "可選角色：business, product, engineering, management, operations, "
                "customer_support, legal, finance, design, qa\n\n"
                "可選 question_intent：technical_constraint, business_process, user_experience, "
                "decision_criteria, compliance, performance, integration, data_flow, workflow, general\n\n"
                "請以 JSON 回應：\n"
                "{\n"
                '  "target_roles": ["適合回答的角色"],\n'
                '  "not_recommended_roles": ["不適合問的角色"],\n'
                '  "expertise_required": ["需要的知識領域"],\n'
                '  "question_intent": "問題意圖類別"\n'
                "}\n\n"
                "規則：\n"
                "- 如果是通用問題（任何角色都能回答），target_roles 為空陣列\n"
                "- 只有明確不適合的角色才放 not_recommended_roles\n"
                "- expertise_required 用英文小寫 snake_case"
            )

            response = openai_service.generate_card_metadata(prompt)

            return {
                "target_roles": response.get("target_roles", []) or [],
                "not_recommended_roles": response.get("not_recommended_roles", []) or [],
                "expertise_required": response.get("expertise_required", []) or [],
                "question_intent": response.get("question_intent", "general") or "general",
            }

        except Exception as e:
            logger.warning(f"Failed to generate role targeting: {e}")
            return {
                "target_roles": [],
                "not_recommended_roles": [],
                "expertise_required": [],
                "question_intent": "general",
            }

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for comparison."""
        import re
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        # Remove punctuation
        text = re.sub(r'[，。、；：！？「」『』（）\s]+', '', text)
        return text.lower()


# Singleton instance
ai_question_generator = AIQuestionGenerator()
