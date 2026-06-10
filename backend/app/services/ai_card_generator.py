"""AI service for generating topic card fields from title and script."""

import logging
from typing import Dict, Any, Optional
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)


class AICardGenerator:
    """Generate topic card metadata from user-provided title and script."""

    def regenerate_suggested_script(
        self,
        title: str,
        description: str = "",
        coverage_rule: Optional[Dict[str, Any]] = None,
        slide_context: str = "",
        current_script: str = "",
    ) -> str:
        """Regenerate only the speaking script for an existing topic card."""
        try:
            prompt = self._build_script_regeneration_prompt(
                title=title,
                description=description,
                coverage_rule=coverage_rule or {},
                slide_context=slide_context,
                current_script=current_script,
            )
            response = openai_service.generate_card_metadata(prompt)
            suggested_script = str(response.get("suggestedScript", "")).strip()
            if not suggested_script:
                raise ValueError("Empty suggestedScript from AI")
            if self._normalize_text(suggested_script) == self._normalize_text(current_script):
                raise ValueError("AI returned the same suggested script")
            return suggested_script[:2000]
        except Exception as e:
            logger.error(f"Failed to regenerate suggested script: {e}")
            raise

    def generate_card_fields(
        self,
        title: str,
        suggested_script: str,
        slide_context: str = ""
    ) -> Dict[str, Any]:
        """
        Generate all topic card fields from title and suggested script.

        Args:
            title: User-provided topic title
            suggested_script: User-provided script for this topic
            slide_context: Optional context from the slide

        Returns:
            Dictionary containing generated fields:
            - description
            - importance
            - topicType
            - coverageRule (with semanticAnchors, expectedKeywords, etc.)
            - estimatedSeconds
        """
        try:
            prompt = self._build_prompt(title, suggested_script, slide_context)
            response = openai_service.generate_card_metadata(prompt)

            return self._parse_response(response, title, suggested_script)

        except Exception as e:
            logger.error(f"Failed to generate card fields: {e}")
            # Return sensible defaults if AI generation fails
            return self._generate_fallback_fields(title, suggested_script)

    def _build_script_regeneration_prompt(
        self,
        title: str,
        description: str,
        coverage_rule: Dict[str, Any],
        slide_context: str,
        current_script: str,
    ) -> str:
        """Build prompt for regenerating one card's speaking script."""
        semantic_anchors = coverage_rule.get("semanticAnchors", [])
        expected_keywords = coverage_rule.get("expectedKeywords", [])
        must_mention_facts = coverage_rule.get("mustMentionFacts", [])
        facts = []
        for fact in must_mention_facts:
            if isinstance(fact, dict):
                text = fact.get("text", "")
                subpoints = fact.get("subpoints") or []
                if subpoints:
                    text = f"{text}（需涵蓋：{'、'.join(subpoints)}）"
                facts.append(text)
            else:
                facts.append(str(fact))
        if not any(str(item).strip() for item in facts):
            facts = semantic_anchors

        return f"""請為以下 Topic Card 重新生成一段自然口語的建議逐字稿。

限制：
- 只重寫這張卡片的逐字稿，不要更改主題方向。
- 優先涵蓋「重要重點」；這是前端顯示與完成度判斷的主要標準。
- 「語意重點」只作為理解主題的背景線索，不需要逐項額外覆蓋。
- 內容要適合演講者直接照著講，語氣自然、清楚。
- 不要新增投影片或背景資料沒有支持的公司名、數字或結論。
- 請換一種說法，不要逐字回傳目前逐字稿。
- 長度控制在 1 到 3 句，最多 2000 字。

卡片標題：
{title}

卡片描述：
{description or "無"}

重要重點（主要覆蓋標準）：
{chr(10).join(f"- {item}" for item in facts if item) if facts else "無"}

語意重點（背景線索，不是額外覆蓋項）：
{chr(10).join(f"- {item}" for item in semantic_anchors) if semantic_anchors else "無"}

預期關鍵字：
{", ".join(expected_keywords) if expected_keywords else "無"}

投影片背景：
{slide_context or "無"}

目前逐字稿參考：
{current_script or "無"}

請只回覆 JSON：
{{
  "suggestedScript": "重新生成後的建議逐字稿"
}}
"""

    def _normalize_text(self, text: str) -> str:
        """Normalize text for same-content checks."""
        return "".join((text or "").split())

    def _build_prompt(self, title: str, script: str, context: str) -> str:
        """Build prompt for OpenAI to generate card metadata."""
        return f"""根據以下資訊，為演講主題卡片生成詳細的元資料：

標題：{title}

建議講稿：
{script}

{f'投影片背景：{context}' if context else ''}

請生成以下內容（以 JSON 格式回覆）：

1. description: 這個主題的簡短描述（1-2 句話，說明演講者需要涵蓋什麼）
2. importance: 重要性等級
   - "must": 絕對必須講到的核心內容
   - "should": 建議要講的重要內容
   - "optional": 可講可不講的補充內容
3. topicType: 主題類型（opening, problem, insight, data, solution, feature, benefit, comparison, risk, result, transition, closing, custom）
4. semanticAnchors: 3-5 個語意錨點（完整句子，描述這個主題的核心概念；作為語意比對線索）
5. expectedKeywords: 10-15 個關鍵字（演講者很可能會說到的詞）
6. mustMentionFacts: 重要重點清單，最多 3 個；前端只顯示 text，請把 semanticAnchors 化約到這 3 個重點內；若父重點底下有必講細節，放到 subpoints
7. estimatedSeconds: 預估講述時間（秒）

範例回覆：
{{
  "description": "介紹 OpenAI API 的計價方式，說明如何根據使用量和功能計費",
  "importance": "must",
  "topicType": "solution",
  "semanticAnchors": [
    "OpenAI API 採用按使用量計費的方式",
    "不同功能和模型有不同的計價標準",
    "使用者只需為實際使用的部分付費"
  ],
  "expectedKeywords": [
    "OpenAI", "API", "計價", "費用", "使用量", "計費", "成本",
    "模型", "功能", "彈性", "付費"
  ],
  "mustMentionFacts": [
    {{
      "text": "根據使用量和功能計費",
      "required": true,
      "aliases": ["使用量計價"],
      "subpoints": ["使用量", "功能差異"]
    }}
  ],
  "estimatedSeconds": 35
}}
"""

    def _parse_response(
        self,
        response: Dict[str, Any],
        title: str,
        script: str
    ) -> Dict[str, Any]:
        """Parse AI response into card fields structure."""

        # Extract basic fields with defaults
        description = response.get('description', f'{title}的相關說明')
        importance = response.get('importance', 'should')
        topic_type = response.get('topicType', 'custom')
        estimated_seconds = response.get('estimatedSeconds', 30)

        # Extract arrays with validation
        semantic_anchors = response.get('semanticAnchors', [])
        if not semantic_anchors:
            semantic_anchors = [f"關於{title}的說明"]

        expected_keywords = response.get('expectedKeywords', [])
        if not expected_keywords:
            # Extract keywords from script
            expected_keywords = self._extract_keywords_from_script(script)

        raw_must_mention_facts = response.get('mustMentionFacts', [])
        must_mention_facts = []
        for fact in raw_must_mention_facts:
            if isinstance(fact, dict):
                text = str(fact.get('text', '')).strip()
                aliases = fact.get('aliases') if isinstance(fact.get('aliases'), list) else []
                subpoints = fact.get('subpoints') if isinstance(fact.get('subpoints'), list) else []
            else:
                text = str(fact).strip()
                aliases = []
                subpoints = []
            if text:
                must_mention_facts.append({
                    "text": text,
                    "required": True,
                    "aliases": aliases,
                    "subpoints": subpoints,
                })
        if not must_mention_facts:
            must_mention_facts = [
                {"text": anchor, "required": True, "aliases": [], "subpoints": []}
                for anchor in semantic_anchors
            ]

        # Build coverage rule
        coverage_rule = {
            "semanticAnchors": semantic_anchors,
            "expectedKeywords": expected_keywords,
            "mustMentionFacts": must_mention_facts,
            "negativeSignals": [],
            "thresholds": {
                "probablyCovered": 0.7,
                "covered": 0.9
            },
            "scoringWeights": {
                "semanticSimilarity": 0.6,
                "keywordCoverage": 0.3,
                "factCoverage": 0.1
            }
        }

        return {
            "description": description,
            "importance": importance,
            "topic_type": topic_type,
            "coverage_rule": coverage_rule,
            "estimated_seconds": estimated_seconds
        }

    def _generate_fallback_fields(
        self,
        title: str,
        script: str
    ) -> Dict[str, Any]:
        """Generate fallback fields when AI generation fails."""

        # Extract simple keywords from script
        keywords = self._extract_keywords_from_script(script)

        # Estimate duration based on script length (rough estimate: 150 words per minute)
        word_count = len(script.split())
        estimated_seconds = max(20, min(180, int(word_count / 2.5)))  # 2.5 words per second

        coverage_rule = {
            "semanticAnchors": [
                f"關於{title}的內容說明",
                script[:100] + "..." if len(script) > 100 else script
            ],
            "expectedKeywords": keywords,
            "mustMentionFacts": [],
            "negativeSignals": [],
            "thresholds": {
                "probablyCovered": 0.7,
                "covered": 0.9
            },
            "scoringWeights": {
                "semanticSimilarity": 0.6,
                "keywordCoverage": 0.3,
                "factCoverage": 0.1
            }
        }

        return {
            "description": f"關於{title}的說明",
            "importance": "should",
            "topic_type": "custom",
            "coverage_rule": coverage_rule,
            "estimated_seconds": estimated_seconds
        }

    def _extract_keywords_from_script(self, script: str) -> list:
        """Extract potential keywords from script text."""
        import re

        # Simple keyword extraction (can be improved with NLP)
        # Remove common words and extract meaningful terms
        common_words = {
            '的', '是', '在', '了', '我', '們', '你', '他', '她', '它',
            '這', '那', '有', '會', '能', '要', '可以', '但是', '因為',
            '所以', '如果', '就', '都', '也', '和', '與', '或', '等'
        }

        # Split into words (simple Chinese character splitting)
        words = re.findall(r'[一-鿿]+|[a-zA-Z]+', script)

        # Filter and count
        word_freq = {}
        for word in words:
            if len(word) >= 2 and word not in common_words:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Get top keywords
        keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in keywords[:15]]


# Singleton instance
ai_card_generator = AICardGenerator()
