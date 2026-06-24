"""AI service for generating question card role targeting."""

import logging
from typing import Dict, Any
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)


class AIQuestionGenerator:
    """Generate question card metadata."""

    def generate_role_targeting(
        self,
        question_text: str,
        question_type: str = "",
        section_context: str = "",
    ) -> Dict[str, Any]:
        """Generate role targeting metadata for a question card."""
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


# Singleton instance
ai_question_generator = AIQuestionGenerator()
