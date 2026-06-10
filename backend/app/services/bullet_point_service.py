"""Bullet Point Generation Service using GPT-5.4 mini."""

import logging
import json
from typing import List
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class BulletPointService:
    """Service for generating bullet points from spoken scripts using GPT-5.4 mini."""

    def __init__(self):
        """Initialize bullet point service."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.SEMANTIC_UNDERSTANDING_MODEL  # gpt-5.4-mini

    def generate_bullet_points(
        self,
        spoken_script: str,
        max_points: int = 5
    ) -> List[str]:
        """
        Convert spoken script to concise bullet points.

        Args:
            spoken_script: Natural language script content
            max_points: Maximum number of bullet points to generate

        Returns:
            List of bullet point strings

        Example:
            >>> service = BulletPointService()
            >>> script = "今天我要介紹機器學習，它包含監督式學習和非監督式學習..."
            >>> points = service.generate_bullet_points(script)
            >>> print(points)
            ['機器學習基本概念', '監督式學習原理', '非監督式學習應用']
        """
        try:
            if not spoken_script or not spoken_script.strip():
                logger.warning("Empty script provided")
                return []

            # Build prompt
            prompt = f"""
請將以下口語化的演講內容，整理成最多 {max_points} 個重點列點。

## 要求
每個列點應該：
1. 簡潔明確（8-20字）
2. 捕捉核心概念和關鍵訊息
3. 適合作為演講時的提示重點
4. 使用清晰的表達，避免冗長
5. 如果某個重點底下有必須講到的子項，請用階層編號輸出：
   - 父重點格式：1. 交易量前三大
   - 子項格式：1-1 台積電、1-2 聯電、1-3 華邦電
   - 子項會作為完成父重點的必要條件，不要把它們改寫成平行父重點

## 演講內容
{spoken_script}

## 輸出格式
請以 JSON 格式回答：
```json
{{
  "bullet_points": [
    "1. 重點1",
    "1-1 子項1",
    "1-2 子項2",
    "2. 重點2"
  ]
}}
```

注意：
- 只提取最重要的核心重點與必要子項
- 保持列點簡潔，易於快速掃視
- 按重要性排序
""".strip()

            # Call GPT-5.4 mini
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是專業的演講重點整理專家，擅長將口語內容提煉成簡潔的重點列表。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3  # Low temperature for consistent output
            )

            # Parse response
            content = response.choices[0].message.content
            result = json.loads(content)
            bullet_points = result.get("bullet_points", [])

            logger.info(
                f"Generated {len(bullet_points)} bullet points from script "
                f"({len(spoken_script)} chars)"
            )

            return bullet_points[:max_points]  # Ensure max_points limit

        except Exception as e:
            logger.error(f"Error generating bullet points: {str(e)}", exc_info=True)
            # Return safe fallback: first sentence as single point
            try:
                first_sentence = spoken_script.split('。')[0][:50]
                return [first_sentence] if first_sentence else []
            except:
                return []


# Singleton instance
bullet_point_service = BulletPointService()
