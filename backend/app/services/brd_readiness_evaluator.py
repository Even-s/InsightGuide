"""BRD Readiness Evaluator - Judges if collected evidence is ready for BRD writing."""

import logging
import json
from typing import List, Dict, Any

from app.services.openai_service import openai_service
from app.models.question_card import QuestionCard

logger = logging.getLogger(__name__)

BRD_READINESS_STATUS = {
    "ready": "足以撰寫正式 BRD 段落",
    "needs_more_detail": "有回答但缺少細節",
    "insufficient": "素材不足，無法撰寫",
    "not_applicable": "此問題不需要出現在 BRD 中",
}


class BRDReadinessEvaluator:
    """Evaluates whether interview evidence is mature enough for BRD generation."""

    def evaluate_readiness(
        self,
        card: QuestionCard,
        criterion_evaluations: List[Dict[str, Any]],
        transcript_context: str = "",  # noqa: ARG002 – reserved for future enriched eval
        theme_title: str = "",
    ) -> Dict[str, Any]:
        """Evaluate BRD readiness for a single card based on its criterion evidence.

        Args:
            card: The question card being evaluated
            criterion_evaluations: Per-criterion evaluation results (from answer eval)
            transcript_context: Relevant transcript text
            theme_title: The interview theme/section title

        Returns:
            Dict with score, status, missing_details, suggested_followups
        """
        # Quick path: if no criteria are satisfied, clearly insufficient
        satisfied_count = sum(
            1 for e in criterion_evaluations
            if e.get("status") in ("satisfied", "partially_satisfied")
        )

        if satisfied_count == 0:
            return {
                "score": 0.0,
                "status": "insufficient",
                "missing_details": ["尚無任何回答內容"],
                "suggested_followups": [],
            }

        # Collect evidence quotes for context
        evidence_quotes = []
        for e in criterion_evaluations:
            quotes = e.get("evidence_quotes", [])
            if quotes:
                evidence_quotes.extend(quotes)

        if not evidence_quotes:
            return {
                "score": 0.1,
                "status": "insufficient",
                "missing_details": ["有回答但缺少可引用的原文證據"],
                "suggested_followups": [],
            }

        # Use LLM to evaluate BRD readiness
        try:
            result = self._llm_evaluate(card, criterion_evaluations, evidence_quotes, theme_title)
            return result
        except Exception as e:
            logger.error(f"BRD readiness evaluation failed: {e}", exc_info=True)
            # Fallback: estimate from criterion coverage
            return self._fallback_evaluate(criterion_evaluations)

    def _llm_evaluate(
        self,
        card: QuestionCard,
        criterion_evaluations: List[Dict[str, Any]],
        evidence_quotes: List[str],
        theme_title: str,
    ) -> Dict[str, Any]:
        """Use LLM to evaluate BRD readiness."""

        criteria_summary = []
        for e in criterion_evaluations:
            criteria_summary.append({
                "criterion_id": e.get("criterion_id"),
                "status": e.get("status"),
                "normalized_value": e.get("normalized_value", ""),
                "has_evidence": bool(e.get("evidence_quotes")),
            })

        system_prompt = (
            "你是 BRD 素材成熟度評估員。判斷訪談蒐集到的回答是否足以撰寫正式 BRD 段落。\n\n"
            "評估標準：\n"
            "1. 是否有具體的事實或數據（而非籠統描述）\n"
            "2. 是否有明確的角色、系統、或流程名稱\n"
            "3. 是否有可量化的資訊（時間、頻率、數量）\n"
            "4. 是否有足夠上下文讓讀者理解需求的背景\n"
            "5. 是否有明確的期望或目標狀態\n\n"
            "score 評分標準：\n"
            "- 0.0-0.3：素材嚴重不足，只有模糊概念\n"
            "- 0.3-0.6：有基本方向但缺少細節或量化\n"
            "- 0.6-0.8：大致足夠，可能缺少量化或角色\n"
            "- 0.8-1.0：素材充分，可直接撰寫正式 BRD 段落\n\n"
            "回傳 JSON 格式：\n"
            "{\"score\": 0.6, \"status\": \"needs_more_detail\", "
            "\"missing_details\": [\"缺少量化時間\", \"缺少涉及角色\"], "
            "\"suggested_followups\": [\"這個步驟通常會花多久？\"]}"
        )

        user_prompt = (
            f"問題：{card.question_text}\n"
            f"焦點：{card.focus_text or ''}\n"
            f"主題：{theme_title}\n\n"
            f"Criteria 狀態：\n{json.dumps(criteria_summary, ensure_ascii=False, indent=2)}\n\n"
            f"已蒐集到的原文證據：\n"
            + "\n".join(f"- {q}" for q in evidence_quotes[:10])
            + "\n\n請評估這些素材是否足以撰寫正式 BRD 段落。只輸出 JSON。"
        )

        response = openai_service.client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        # Validate and normalize
        score = float(result.get("score", 0.0))
        score = max(0.0, min(1.0, score))

        # Determine status from score if not provided
        status = result.get("status")
        if not status:
            if score >= 0.8:
                status = "ready"
            elif score >= 0.4:
                status = "needs_more_detail"
            else:
                status = "insufficient"

        return {
            "score": score,
            "status": status,
            "missing_details": result.get("missing_details", []) or [],
            "suggested_followups": result.get("suggested_followups", []) or [],
        }

    def _fallback_evaluate(
        self,
        criterion_evaluations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Fallback evaluation when LLM is unavailable."""
        total = len(criterion_evaluations)
        if total == 0:
            return {"score": 0.0, "status": "insufficient", "missing_details": [], "suggested_followups": []}

        satisfied = sum(1 for e in criterion_evaluations if e.get("status") == "satisfied")
        partial = sum(1 for e in criterion_evaluations if e.get("status") == "partially_satisfied")

        score = (satisfied + partial * 0.3) / total

        if score >= 0.8:
            status = "ready"
        elif score >= 0.4:
            status = "needs_more_detail"
        else:
            status = "insufficient"

        missing = [
            e.get("criterion_id", "unknown")
            for e in criterion_evaluations
            if e.get("status") in ("not_addressed", "attempted_but_unresolved")
        ]

        return {
            "score": round(score, 2),
            "status": status,
            "missing_details": [f"criterion {m} 尚未被充分回答" for m in missing],
            "suggested_followups": [],
        }

    def batch_evaluate(
        self,
        cards_with_evaluations: List[Dict[str, Any]],
        transcript_context: str = "",
    ) -> List[Dict[str, Any]]:
        """Evaluate BRD readiness for multiple cards.

        Args:
            cards_with_evaluations: List of dicts with 'card', 'criterion_evaluations', 'theme_title'
            transcript_context: Full transcript for context

        Returns:
            List of readiness results, one per card
        """
        results = []
        for item in cards_with_evaluations:
            result = self.evaluate_readiness(
                card=item["card"],
                criterion_evaluations=item.get("criterion_evaluations", []),
                transcript_context=transcript_context,
                theme_title=item.get("theme_title", ""),
            )
            results.append(result)
        return results


# Singleton instance
brd_readiness_evaluator = BRDReadinessEvaluator()
