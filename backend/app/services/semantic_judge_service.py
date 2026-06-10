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

            # Call semantic model (GPT-5.4-mini) with structured output for fast real-time matching
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是簡報分析的語義理解專家。你的任務是判斷演講者的發言是否從語義上覆蓋了"
                                   "投影片中的特定主題。使用深度語義理解，不要求逐字匹配，理解意思相近即可。"
                                   "只回覆結構化的 JSON 格式。"
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

    def batch_judge_candidates(
        self,
        utterance_text: str,
        candidate_cards: list,
        session_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Judge multiple candidate cards for a single utterance.

        More efficient than calling judge_coverage multiple times
        when you have multiple candidate cards.

        Args:
            utterance_text: The transcribed utterance
            candidate_cards: List of candidate topic card objects

        Returns:
            Dict mapping card_id to judgment result

        Example:
            >>> results = service.batch_judge_candidates(utterance, cards)
            >>> for card_id, judgment in results.items():
            ...     print(f"Card {card_id}: {judgment['is_covered']}")
        """
        results = {}

        for card in candidate_cards:
            card_id = card.get('id', '')
            judgment = self.judge_coverage(utterance_text, card, session_id=session_id)
            results[card_id] = judgment

        return results

    def judge_completion_percentage(
        self,
        transcript_context: str,
        topic_card: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ask GPT-5.4-mini to score how much of a topic card has been completed.

        Unlike judge_coverage(), this is designed for live card progress:
        it looks at the speaker's accumulated transcript so far and returns
        a percentage that can drive the card water level directly.
        """
        try:
            title = topic_card.get('title', '')
            description = topic_card.get('description', '')
            coverage_rule = topic_card.get('coverageRule', {})
            semantic_anchors = coverage_rule.get('semanticAnchors', [])
            expected_keywords = coverage_rule.get('expectedKeywords', [])
            must_mention_facts = coverage_rule.get('mustMentionFacts', [])

            important_points = []
            for index, fact in enumerate(must_mention_facts):
                text = fact.get('text', '') if isinstance(fact, dict) else str(fact)
                if not text:
                    continue
                required = fact.get('required', True) if isinstance(fact, dict) else True
                aliases = fact.get('aliases') or [] if isinstance(fact, dict) else []
                subpoints = fact.get('subpoints') or [] if isinstance(fact, dict) else []
                line = f"- fact_{index}: {text}"
                if required:
                    line += " (必須)"
                if aliases:
                    line += f" [別名: {', '.join(aliases)}]"
                if subpoints:
                    line += f" [完成此重點必須講到: {', '.join(subpoints)}]"
                important_points.append(line)

            if important_points:
                aspect_ids = {}
                for index, fact in enumerate(must_mention_facts):
                    if not fact:
                        continue
                    text = fact.get('text', '') if isinstance(fact, dict) else str(fact)
                    subpoints = fact.get('subpoints') or [] if isinstance(fact, dict) else []
                    if subpoints:
                        text = f"{text}（必須完整講到：{'、'.join(subpoints)}）"
                    aspect_ids[f"fact_{index}"] = text
            else:
                aspect_ids = {
                    f"anchor_{index}": anchor
                    for index, anchor in enumerate(semantic_anchors)
                    if anchor
                }
                important_points = [
                    f"- anchor_{index}: {anchor}"
                    for index, anchor in enumerate(semantic_anchors)
                    if anchor
                ]

            aspect_reference = "\n".join(
                f"- {aspect_id}: {text}" for aspect_id, text in aspect_ids.items() if text
            )

            prompt = f"""
請根據「到目前為止的演講逐字稿」，判斷下面這張主題卡片已完成多少百分比。

你要評分的是「這張卡片要求的內容是否已被講到」，不是逐字相似度。
允許口語改寫、同義詞、順序不同；必要事實用來判斷能否接近 100%，但不要因為缺少精確數字就把已完整講過的主題壓到很低。

## 主題卡片
標題: {title}
描述: {description}

核心語義錨點（只作為語意比對線索，不是獨立計分項）:
{chr(10).join(f'- anchor_{index}: {anchor}' for index, anchor in enumerate(semantic_anchors)) if semantic_anchors else '(無)'}

預期關鍵詞:
{', '.join(expected_keywords) if expected_keywords else '(無)'}

重要重點（完成度只看這份清單）:
{chr(10).join(important_points) if important_points else '(無)'}

列點 ID 對照表:
{aspect_reference if aspect_reference else '(無)'}

## 到目前為止的演講逐字稿
{transcript_context}

## 評分規則
- 0-19: 幾乎沒有提到
- 20-39: 只講到單一重要重點或剛開始切入主題
- 40-59: 有碰到相關方向，但只涵蓋部分重要重點
- 60-79: 已講到主要方向或一半以上重要重點，但仍缺重要細節
- 80-89: 大致完成核心主題，但仍有少數數字、個股或細節可補
- 90-100: 已充分完成這張卡片，且沒有重要缺漏；必講事實也已提到

重要：
- 只講到其中一個重要重點時，不可判定 complete，分數通常應落在 20-45。
- 如果演講者已涵蓋交易量、振幅/波動、漲幅、跌幅、資金集中/市場熱度等多個核心面向，即使沒有精確數字，也應給 70-85。
- 如果演講者提到必講事實的主體與方向，但漏掉精確數字，可以視為大致完成，但除非沒有重要缺漏，否則不要給 90 以上。
- is_complete 只有在上方「重要重點」都已涵蓋時才可為 true。
- 若某個重要重點列出「完成此重點必須講到」的子項，必須所有子項都已被逐字稿涵蓋，才可以把該 fact_* 放進 covered_aspect_ids。
- 例如 fact_0 是「交易量前三大」，子項是「台積電、聯電、華邦電」時，只講到台積電或只講到交易量前三大，都不可判定 fact_0 covered；必須三檔都講到。
- covered_aspect_ids 和 missing_aspect_ids 只能填入上方「列點 ID 對照表」裡的 id；有 fact_* 時不可回傳 anchor_*。
- 若某個列點只被部分提到但還未完整表達，請放在 missing_aspect_ids，不要放在 covered_aspect_ids。
- 只有完全沒談到卡片主題，才給 0-19。

請只回覆 JSON：
{{
  "completion_percentage": 0-100 的整數,
  "confidence": 0.0-1.0,
  "is_complete": boolean,
  "reasoning": "簡短說明，引用逐字稿中的實際內容",
  "covered_aspects": ["已涵蓋面向"],
  "missing_aspects": ["還缺的面向"],
  "covered_aspect_ids": ["已完整講完的列點 id"],
  "missing_aspect_ids": ["尚未完整講完的列點 id"]
}}
""".strip()

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是簡報主題卡片完成度評分器。只根據逐字稿和卡片要求評分，並只回傳 JSON。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            billing_service.record_chat_completion(
                presentation_session_id=session_id,
                operation="card_completion_judgment",
                model=self.model,
                response=response,
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            percentage = int(round(float(result.get('completion_percentage', 0) or 0)))
            percentage = max(0, min(100, percentage))
            confidence = float(result.get('confidence', percentage / 100) or 0.0)
            confidence = max(0.0, min(1.0, confidence))
            valid_aspect_ids = set(aspect_ids.keys())
            covered_aspect_ids = [
                aspect_id
                for aspect_id in result.get('covered_aspect_ids', [])
                if aspect_id in valid_aspect_ids
            ]
            missing_aspect_ids = [
                aspect_id
                for aspect_id in result.get('missing_aspect_ids', [])
                if aspect_id in valid_aspect_ids
            ]

            normalized = {
                'completion_percentage': percentage,
                'confidence': confidence,
                'is_complete': (
                    bool(result.get('is_complete', False))
                    and percentage >= 85
                    and not result.get('missing_aspects', [])
                ),
                'reasoning': result.get('reasoning', ''),
                'covered_aspects': result.get('covered_aspects', []),
                'missing_aspects': result.get('missing_aspects', []),
                'covered_aspect_ids': covered_aspect_ids,
                'missing_aspect_ids': missing_aspect_ids,
            }

            logger.info(
                "Card completion judgment (%s): completion=%s%% confidence=%.2f complete=%s",
                self.model,
                normalized['completion_percentage'],
                normalized['confidence'],
                normalized['is_complete'],
            )

            return normalized

        except Exception as e:
            logger.error(f"Error in card completion judgment: {str(e)}", exc_info=True)
            return {
                'completion_percentage': 0,
                'confidence': 0.0,
                'is_complete': False,
                'reasoning': f'Error during completion judgment: {str(e)}',
                'covered_aspects': [],
                'missing_aspects': [],
                'covered_aspect_ids': [],
                'missing_aspect_ids': []
            }

    def judge_script_match(
        self,
        expected_text: str,
        actual_text: str,
        keywords: list = None
    ) -> Dict[str, Any]:
        """
        使用 GPT-5.4-mini 判斷使用者說的話是否匹配建議句（Script Plan 專用）

        完全語意判斷，不依賴簡單規則。

        Args:
            expected_text: 建議句的內容
            actual_text: 使用者實際說的話
            keywords: 關鍵詞列表（可選，輔助判斷）

        Returns:
            Dict with:
            - action: str - "advance" | "hold"
            - confidence: float - 信心分數 (0-1)
            - reasoning: str - 判斷理由
            - semantic_similarity: float - 語意相似度 (0-1)
        """
        try:
            # 建構提示詞
            keywords_text = f"\n關鍵詞: {', '.join(keywords)}" if keywords else ""

            prompt = f"""請判斷使用者說的話是否與建議句語意匹配。

**建議句**（期望內容）:
{expected_text}
{keywords_text}

**使用者說的話**（實際內容）:
{actual_text}

## 判斷標準

1. **語意相同或相近** → action: "advance"
   - 核心意思相同或相近
   - 允許換個說法（paraphrase）
   - 允許省略部分細節
   - 允許詞序不同
   - 允許口語化表達

   範例：
   - 建議："交易量很高，代表市場關注度強"
   - 實際："市場關注度是強的"
   - 判斷：advance（核心意思表達出來了）

2. **完全不相關或不清楚** → action: "hold"
   - 主題完全不同
   - 沒有提到任何相關概念
   - 只說了測試用語（"測試"、"嗯"、"啊"）

## 回傳格式

JSON 格式：
{{
  "action": "advance" | "hold",
  "confidence": 0.0-1.0,
  "reasoning": "判斷理由（簡短一句話）",
  "semantic_similarity": 0.0-1.0
}}

## 重要原則

- **寬鬆判斷**：優先判斷為 "advance"，除非明顯不匹配
- **語意優先**：注重核心意思，不要求字詞完全一致
- **使用者友好**：換個說法也算匹配

請判斷："""

            # 調用 GPT-5.4-mini（快速語意判斷）
            response = self.client.chat.completions.create(
                model=self.model,  # gpt-5.4-mini
                messages=[
                    {
                        "role": "system",
                        "content": "你是語意匹配專家。判斷兩句話是否表達相同或相近的意思。"
                                   "要寬鬆判斷，允許換個說法。只回傳 JSON 格式。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.2  # 低溫度，更一致的判斷
            )

            # 解析回應
            content = response.choices[0].message.content
            result = json.loads(content)

            logger.info(
                f"[SemanticJudge] Script match: action={result.get('action')}, "
                f"confidence={result.get('confidence', 0):.2f}, "
                f"similarity={result.get('semantic_similarity', 0):.2f}, "
                f"reason={result.get('reasoning', '')[:50]}"
            )

            return result

        except Exception as e:
            logger.error(f"Script match judgment error: {e}", exc_info=True)
            # Fallback: 保守判斷為 hold
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reasoning': f"Error during judgment: {str(e)}",
                'semantic_similarity': 0.0
            }

    def judge_script_progression_mode(
        self,
        current_text: str,
        actual_text: str,
        next_texts: list = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lightweight Script Plan progression scorer.

        Returns:
        - mode: advance | hold | regenerate
        - coverage: 0-100, how much the current suggestion is covered
        - reason_code: matched | partial | filler | off_topic | unclear
        """
        try:
            next_texts = next_texts or []
            next_context = "\n".join(f"- {text}" for text in next_texts[:2]) or "(無)"

            prompt = f"""判斷演講逐字稿相對於目前建議句的覆蓋程度。

目前建議句:
{current_text}

後續建議方向:
{next_context}

演講者剛說:
{actual_text}

只回 JSON：
{{
  "mode": "advance" | "hold" | "regenerate",
  "coverage": 0-100,
  "reason_code": "matched" | "partial" | "filler" | "off_topic" | "unclear"
}}

判斷規則：
- coverage >= 60 且核心意思已涵蓋目前建議：mode=advance, reason_code=matched
- coverage 30-59 或只講到一部分：mode=hold, reason_code=partial
- 寒暄、填充、半句、語意不完整：mode=hold, reason_code=filler 或 unclear
- 明顯偏離目前建議與後續方向：mode=regenerate, reason_code=off_topic
""".strip()

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是即時簡報提示評分器。只回 JSON，不解釋。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0
            )
            billing_service.record_chat_completion(
                presentation_session_id=session_id,
                operation="script_progression_judgment",
                model=self.model,
                response=response,
            )

            content = response.choices[0].message.content
            result = json.loads(content)
            mode = result.get("mode", "hold")
            if mode not in {"advance", "hold", "regenerate"}:
                mode = "hold"

            try:
                coverage = int(round(float(result.get("coverage", 0) or 0)))
            except (TypeError, ValueError):
                coverage = 0
            coverage = max(0, min(100, coverage))

            reason_code = result.get("reason_code", "unclear")
            if reason_code not in {"matched", "partial", "filler", "off_topic", "unclear"}:
                reason_code = "unclear"

            logger.info(
                "[SemanticJudge] Script progression: mode=%s coverage=%s reason=%s",
                mode,
                coverage,
                reason_code,
            )
            return {"mode": mode, "coverage": coverage, "reason_code": reason_code}

        except Exception as e:
            logger.error(f"Script progression mode judgment error: {e}", exc_info=True)
            return {"mode": "hold", "coverage": 0, "reason_code": "unclear"}

    def clean_spoken_script(self, raw_text: str) -> str:
        """Clean dictated topic-card script while preserving the user's content."""
        text = (raw_text or "").strip()
        if not text:
            return ""

        try:
            prompt = f"""請清理以下由語音轉錄而來的講稿內容。

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
                        "content": "你是繁體中文簡報講稿編輯器。只做保守清理，不改寫成新內容，並只回 JSON。"
                    },
                    {
                        "role": "user",
                        "content": prompt
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
