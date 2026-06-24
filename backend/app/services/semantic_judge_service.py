"""Semantic judge service for text cleanup using LLM."""

import logging
import json
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class SemanticJudgeService:
    """Service for LLM-powered text processing (spoken script cleanup)."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.SEMANTIC_UNDERSTANDING_MODEL

    def clean_spoken_script(self, raw_text: str) -> str:
        """Clean dictated topic-card script while preserving the user's content."""
        text = (raw_text or "").strip()
        if not text:
            return ""

        try:
            system_prompt = "你是繁體中文簡報講稿編輯器。只做保守清理，不改寫成新內容，並只回 JSON。"
            user_prompt = f"""請清理以下由語音轉錄而來的講稿內容。

原則：
- 盡量不改變使用者原本要表達的內容、順序與語氣。
- 修正明顯語音辨識錯字、標點、斷句、重複詞、口頭禪與不必要填充詞。
- 不要新增原文沒有的資訊、數字、公司名或結論。
- 保留專有名詞、產品名、股票名、英文縮寫與重要數字。
- 輸出仍要適合放在 Topic Card 的「建議講稿」欄位。

語音轉錄：
{text}

請只回覆 JSON：
{{
  "cleaned_text": "清理後文字"
}}
""".strip()

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            result = json.loads(response.choices[0].message.content)
            cleaned_text = str(result.get("cleaned_text", "")).strip()
            return cleaned_text or text
        except Exception as e:
            logger.error("Spoken script cleanup failed: %s", str(e), exc_info=True)
            return text


# Singleton instance
semantic_judge_service = SemanticJudgeService()
