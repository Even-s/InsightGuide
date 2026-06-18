"""Semantic judge service for deep understanding using configurable LLM."""

import logging
import json
from typing import Dict, Any, Optional
from openai import OpenAI

from app.core.config import settings
from app.services.billing_service import billing_service

logger = logging.getLogger(__name__)


class SemanticJudgeService:
    """
    Service for semantic understanding and coverage judgment.

    Currently uses GPT-5.4-mini (configured via SEMANTIC_UNDERSTANDING_MODEL) for fast real-time matching.
    Provides deep semantic analysis to determine if speaker utterances
    cover topic card content.
    """

    def __init__(self):
        """Initialize semantic judge service with configured model (GPT-5.4-mini for speed)."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.SEMANTIC_UNDERSTANDING_MODEL  # gpt-5.4-mini

    def judge_coverage(
        self,
        utterance_text: str,
        topic_card: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Use semantic LLM (GPT-5.4-mini) to judge if utterance covers the topic card.

        Returns structured JSON with judgment, confidence, and reasoning.

        Args:
            utterance_text: The transcribed utterance
            topic_card: Topic card object with title, description, coverageRule

        Returns:
            Dict with:
            - is_covered: bool - Whether topic is covered
            - confidence: float - Confidence score (0-1)
            - reasoning: str - Explanation of the judgment
            - mentioned_keywords: list - Keywords that were mentioned
            - missing_aspects: list - Important aspects not covered

        Example:
            >>> result = service.judge_coverage(
            ...     "今天介紹機器學習的監督式和非監督式學習",
            ...     topic_card
            ... )
            >>> result['is_covered']
            True
            >>> result['confidence']
            0.92
        """
        try:
            # Extract card information
            title = topic_card.get('title', '')
            description = topic_card.get('description', '')
            coverage_rule = topic_card.get('coverageRule', {})
            semantic_anchors = coverage_rule.get('semanticAnchors', [])
            expected_keywords = coverage_rule.get('expectedKeywords', [])
            must_mention_facts = coverage_rule.get('mustMentionFacts', [])

            # Build prompt
            prompt = self._build_judge_prompt(
                utterance_text=utterance_text,
                title=title,
                description=description,
                semantic_anchors=semantic_anchors,
                expected_keywords=expected_keywords,
                must_mention_facts=must_mention_facts
            )

            system_prompt = (
                "你是簡報分析的語義理解專家。你的任務是判斷演講者的發言是否從語義上覆蓋了"
                "投影片中的特定主題。使用深度語義理解，不要求逐字匹配，理解意思相近即可。"
                "只回覆結構化的 JSON 格式。"
            )

            # Call semantic model (GPT-5.4-mini) with structured output for fast real-time matching
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3  # Lower temperature for faster, more consistent responses
            )
            billing_service.record_chat_completion(
                presentation_session_id=session_id,
                operation="coverage_judgment",
                model=self.model,
                response=response,
            )

            # Parse response
            content = response.choices[0].message.content
            result = json.loads(content)

            logger.info(
                f"Semantic judgment ({self.model}): is_covered={result.get('is_covered')}, "
                f"confidence={result.get('confidence'):.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"Error in semantic judgment: {str(e)}")
            # Return safe default
            return {
                'is_covered': False,
                'confidence': 0.0,
                'reasoning': f'Error during judgment: {str(e)}',
                'mentioned_keywords': [],
                'missing_aspects': []
            }

    def _build_judge_prompt(
        self,
        utterance_text: str,
        title: str,
        description: str,
        semantic_anchors: list,
        expected_keywords: list,
        must_mention_facts: list
    ) -> str:
        """Build the prompt for GPT-5.4-mini judgment with fast semantic understanding."""

        # Format facts
        facts_text = ""
        if must_mention_facts:
            facts_list = []
            for fact in must_mention_facts:
                fact_str = f"- {fact.get('text', '')}"
                if fact.get('required', True):
                    fact_str += " (必須提及)"
                if fact.get('aliases'):
                    fact_str += f" [別名: {', '.join(fact['aliases'])}]"
                if fact.get('subpoints'):
                    fact_str += f" [完成此事實必須講到: {', '.join(fact['subpoints'])}]"
                facts_list.append(fact_str)
            facts_text = "\n".join(facts_list)

        prompt = f"""
你是需求訪談評估專家，負責判斷受訪者的回答是否從**語義層面**充分回應了提問重點，使其足以寫入正式 BRD 文件。

## 提問重點資訊

**提問重點**: {title}

**問題類型**: {description}

**核心語義錨點** (需要被回答的核心概念):
{chr(10).join(f'- {anchor}' for anchor in semantic_anchors) if semantic_anchors else '(無)'}

**預期關鍵詞** (回答中可能出現的詞彙):
{', '.join(expected_keywords) if expected_keywords else '(無)'}

**期待回答要素** (BRD 需要的具體資訊):
{facts_text if facts_text else '(無)'}

## 受訪者的回答

"{utterance_text}"

## 判斷原則

請使用深度語義理解，而非表面字詞匹配：

1. **語義等價性**:
   - 接受不同表達方式，只要意思相近
   - 口語化表達等同於書面語表達
   - 回答不需要逐字對應問題，只要資訊足夠即可

2. **BRD 充分性判斷**:
   - **足以撰寫 BRD** (confidence > 0.8): 回答包含具體流程、規則、數據，可直接寫入正式文件
   - **基本足夠** (confidence 0.6-0.8): 核心概念有回答，但缺少部分細節
   - **部分提及** (confidence 0.3-0.6): 只提到相關概念，資訊不足以寫入 BRD
   - **未回答** (confidence < 0.3): 沒有提供相關資訊

3. **重要提醒**:
   - 訪談者提出問題本身不算回答，只有受訪者的實質描述才算
   - 判斷依據是「能否根據這段回答寫出 BRD 段落」

## 請回答

以 JSON 格式回答:

```json
{{
  "is_covered": boolean,          // 回答是否足以寫入 BRD (confidence >= 0.6 時為 true)
  "confidence": float,            // 充分度 (0.0-1.0)
  "reasoning": string,            // 判斷理由
  "mentioned_keywords": [string], // 受訪者實際提到的關鍵詞
  "missing_aspects": [string]     // 尚未回答的重要面向
}}
```

現在請分析上述的受訪者回答與提問重點。
""".strip()

        return prompt


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
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
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
