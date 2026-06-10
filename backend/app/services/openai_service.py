"""OpenAI API integration service for slide analysis and topic card generation."""

import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.billing_service import billing_service

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI APIs."""

    def __init__(self):
        """Initialize OpenAI client."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=60.0)
        self.analysis_model = settings.DOCUMENT_ANALYSIS_MODEL
        self.embedding_model = settings.EMBEDDING_MODEL

    def analyze_section(
        self,
        slide_number: int,
        slide_image_url: str,
        extracted_text: str,
        speaker_notes: Optional[str] = None,
        deck_context: Optional[str] = None,
        slide_image_base64: Optional[str] = None,
        deck_id: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a single slide and generate topic cards.

        Args:
            slide_number: The page number of the slide
            slide_image_url: URL to the slide image (deprecated, use slide_image_base64 for local testing)
            extracted_text: Text extracted from the slide
            speaker_notes: Optional speaker notes
            deck_context: Optional context about the entire deck
            slide_image_base64: Base64-encoded image data (preferred for local testing)

        Returns:
            Dict containing analysis results with topic cards
        """
        logger.info(f"Analyzing slide {slide_number}")

        # Build the prompt for slide analysis
        prompt = self._build_analysis_prompt(
            slide_number=slide_number,
            extracted_text=extracted_text,
            speaker_notes=speaker_notes,
            deck_context=deck_context
        )

        # Determine image source
        if slide_image_base64:
            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{slide_image_base64}",
                    "detail": "high"
                }
            }
            logger.info(f"Using base64-encoded image for slide {slide_number}")
        else:
            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": slide_image_url,
                    "detail": "high"
                }
            }
            logger.info(f"Using URL image for slide {slide_number}: {slide_image_url}")

        try:
            # Call OpenAI API with vision and structured output
            request_params = {
                "model": self.analysis_model,
                "messages": [
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            image_content
                        ]
                    }
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "slide_analysis",
                        "strict": True,
                        "schema": self._get_analysis_schema()
                    }
                },
                "max_completion_tokens": 4096
            }
            if not self._uses_default_temperature_only(self.analysis_model):
                request_params["temperature"] = 0.7

            response = self.client.chat.completions.create(**request_params)
            billing_service.record_deck_chat_completion(
                deck_id=deck_id,
                operation="slide_analysis_topic_card_generation",
                model=self.analysis_model,
                response=response,
                source_id=source_id or f"slide:{slide_number}",
            )

            # Parse the structured response
            import json
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Successfully analyzed slide {slide_number}, generated {len(result.get('topicCards', []))} cards")
            return result

        except Exception as e:
            logger.error(f"Error analyzing slide {slide_number}: {str(e)}")
            raise

    def _get_system_prompt(self) -> str:
        """Get the system prompt for section analysis."""
        return """你是 InsightGuide 的需求文件分析專家。你的任務是分析需求文件內容，產出訪談問題卡片(Question Cards)。

你需要：
1. 理解章節的核心訊息與關鍵需求
2. 為每個重要主題產生一張 Question Card（最多3張）
3. 為每張卡片設定覆蓋規則(Coverage Rules)，包括：
   - semanticAnchors: 語意錨點，描述這個主題的核心意思（1-3句，作為語意比對線索）
   - expectedKeywords: 預期會出現的關鍵字（5-15個）
  - mustMentionFacts: 前端顯示與完成度計分用的重要重點（最多 3 個；text 必須是短標籤，不要寫成完整長句；細節放到 subpoints）
   - negativeSignals: 不應該出現的內容（可選）
4. 建議每張卡片的講稿
5. 估計每張卡片需要講多久（秒數）

重要原則：
- 優先挑選 "must" 重要度的主題
- Coverage rules 要具體，便於後續語意比對
- 關鍵字要考慮同義詞和相關詞
- mustMentionFacts 是簡報模式顯示與水位計分的唯一列點；不要留空，但最多 3 個，請將 semanticAnchors 化約到這 3 個重要重點內
- mustMentionFacts.text 必須短、可掃讀、像卡片 bullet 標題，建議 8-24 個中文字；不要寫「需要說明...」「重點結論是...」這種完整句
- 如果一個前端顯示重點底下有多個必講細節，請把顯示名稱放在 text，細節放到 subpoints；subpoints 最多 3 個，每個也要短；例如 text="交易量前三大"，subpoints=["台積電","聯電","華邦電"]
- 必提事實應該包含具體的數據、名稱、關鍵結論；若沒有數據，也要列出核心概念重點
- 建議講稿應該自然、口語化
- 估計秒數要合理（usually 20-45 seconds per card）

請只輸出符合 JSON schema 的結果。"""

    def _build_analysis_prompt(
        self,
        slide_number: int,
        extracted_text: str,
        speaker_notes: Optional[str],
        deck_context: Optional[str]
    ) -> str:
        """Build the analysis prompt for a slide."""
        prompt_parts = [
            f"請分析第 {slide_number} 頁投影片。",
            "",
            "投影片文字內容：",
            extracted_text if extracted_text else "（無文字內容）",
            ""
        ]

        if speaker_notes:
            prompt_parts.extend([
                "備註欄內容：",
                speaker_notes,
                ""
            ])

        if deck_context:
            prompt_parts.extend([
                "簡報整體背景：",
                deck_context,
                ""
            ])

        prompt_parts.extend([
            "請產生這一頁的 Topic Cards（最多3張）。",
            "每張卡片都需要包含完整的 Coverage Rules，以便後續演講時進行語意比對。",
            "",
            "請特別注意：",
            "- semanticAnchors 要描述這個主題應該講什麼核心概念，作為語意比對線索",
            "- expectedKeywords 要涵蓋可能的說法和同義詞",
            "- mustMentionFacts 是前端顯示與完成度計分用的重要重點；最多 3 個，每個 text 都要是短標籤，不要是完整長句",
            "- 若重要重點包含多個必講子項，請用 subpoints 表示；subpoints 最多 3 個，每個都要短；父重點只有在 subpoints 全部被講到時才算完成",
            "- 建議講稿要自然、口語化，符合台灣簡報習慣",
            "- 根據內容複雜度合理估計講解時間"
        ])

        return "\n".join(prompt_parts)

    def _get_analysis_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for structured output."""
        return {
            "type": "object",
            "properties": {
                "slideSummary": {
                    "type": "string",
                    "description": "這一頁投影片的整體摘要（1-2句話）"
                },
                "topicCards": {
                    "type": "array",
                    "description": "這一頁的重點卡片（最多3張）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "卡片標題（簡短精確，最多80字元）"
                            },
                            "description": {
                                "type": "string",
                                "description": "卡片描述（解釋這個主題的內容，最多500字元）"
                            },
                            "importance": {
                                "type": "string",
                                "enum": ["must", "should", "optional"],
                                "description": "重要程度：must=必講, should=建議講, optional=可選"
                            },
                            "topicType": {
                                "type": "string",
                                "enum": [
                                    "opening", "problem", "insight", "data",
                                    "solution", "feature", "benefit", "comparison",
                                    "risk", "result", "transition", "closing", "custom"
                                ],
                                "description": "主題類型"
                            },
                            "coverageRule": {
                                "type": "object",
                                "properties": {
                                    "semanticAnchors": {
                                        "type": "array",
                                        "description": "語意錨點：1-3句話描述這個主題的核心意思",
                                        "items": {"type": "string"},
                                        "minItems": 1,
                                        "maxItems": 8
                                    },
                                    "expectedKeywords": {
                                        "type": "array",
                                        "description": "預期關鍵字：包括同義詞和相關詞，5-15個",
                                        "items": {"type": "string"}
                                    },
                                    "mustMentionFacts": {
                                        "type": "array",
                                        "description": "重要重點：前端顯示與完成度計分用，最多 3 個；細節請放 subpoints",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "text": {
                                                    "type": "string",
                                                    "maxLength": 48,
                                                    "description": "必須提到的事實"
                                                },
                                                "required": {
                                                    "type": "boolean",
                                                    "description": "是否必須提到"
                                                },
                                                "aliases": {
                                                    "type": "array",
                                                    "description": "這個事實的其他說法",
                                                    "items": {"type": "string"}
                                                },
                                                "subpoints": {
                                                    "type": "array",
                                                    "description": "完成此顯示重點前必須講到的子項；例如交易量前三大的三檔股票",
                                                    "items": {"type": "string", "maxLength": 48},
                                                    "maxItems": 3
                                                }
                                            },
                                            "required": ["text", "required", "aliases", "subpoints"],
                                            "additionalProperties": False
                                        },
                                        "maxItems": 3
                                    },
                                    "negativeSignals": {
                                        "type": "array",
                                        "description": "負面信號：如果出現這些內容，可能是誤判",
                                        "items": {"type": "string"}
                                    },
                                    "thresholds": {
                                        "type": "object",
                                        "properties": {
                                            "probablyCovered": {
                                                "type": "number",
                                                "description": "可能已講到的閾值（0-1）"
                                            },
                                            "covered": {
                                                "type": "number",
                                                "description": "確定已講到的閾值（0-1）"
                                            }
                                        },
                                        "required": ["probablyCovered", "covered"],
                                        "additionalProperties": False
                                    },
                                    "scoringWeights": {
                                        "type": "object",
                                        "properties": {
                                            "semanticSimilarity": {"type": "number"},
                                            "keywordCoverage": {"type": "number"},
                                            "factCoverage": {"type": "number"}
                                        },
                                        "required": ["semanticSimilarity", "keywordCoverage", "factCoverage"],
                                        "additionalProperties": False
                                    }
                                },
                                "required": ["semanticAnchors", "expectedKeywords", "mustMentionFacts", "negativeSignals", "thresholds", "scoringWeights"],
                                "additionalProperties": False
                            },
                            "suggestedScript": {
                                "type": "string",
                                "description": "建議的講稿（口語化，自然的說法）"
                            },
                            "estimatedSeconds": {
                                "type": "integer",
                                "description": "估計需要講多久（秒數，通常20-45秒）"
                            },
                            "orderIndex": {
                                "type": "integer",
                                "description": "在這一頁中的順序（0開始）"
                            }
                        },
                        "required": [
                            "title", "description", "importance", "topicType",
                            "coverageRule", "suggestedScript", "estimatedSeconds", "orderIndex"
                        ],
                        "additionalProperties": False
                    },
                    "maxItems": 3
                }
            },
            "required": ["slideSummary", "topicCards"],
            "additionalProperties": False
        }

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        try:
            logger.info(f"Generating embeddings for {len(texts)} texts")
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            embeddings = [item.embedding for item in response.data]
            logger.info(f"Successfully generated {len(embeddings)} embeddings")
            return embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise


# Singleton instance
    def generate_card_metadata(self, prompt: str) -> Dict[str, Any]:
        """
        Generate topic card metadata using the configured slide analysis model.

        Args:
            prompt: The prompt describing what metadata to generate

        Returns:
            Dictionary containing generated metadata fields
        """
        try:
            request_params = {
                "model": self.analysis_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing presentation content and generating structured metadata for topic cards. Always respond with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "response_format": {"type": "json_object"},
            }
            if not self._uses_default_temperature_only(self.analysis_model):
                request_params["temperature"] = 0.7

            response = self.client.chat.completions.create(**request_params)

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from OpenAI")

            import json
            return json.loads(content)

        except Exception as e:
            logger.error(f"Failed to generate card metadata: {e}")
            raise

    def _uses_default_temperature_only(self, model: str) -> bool:
        """Return True for models that reject custom temperature values."""
        return model.startswith("gpt-5")

    def analyze_document_section(
        self,
        section_text: str,
        section_title: Optional[str] = None,
        document_title: Optional[str] = None,
        section_number: int = 1,
    ) -> Dict[str, Any]:
        """
        Analyze a document section and generate interview questions.

        Args:
            section_text: Text content of the section
            section_title: Title of the section
            document_title: Title of the document
            section_number: Section number in the document

        Returns:
            Dict containing:
                - summary: AI-generated summary of the section
                - questions: List of question cards with metadata
                - usage: Token usage information
        """
        logger.info(f"Analyzing document section {section_number}")

        # Build the analysis prompt
        prompt = self._build_document_analysis_prompt(
            section_text=section_text,
            section_title=section_title,
            document_title=document_title,
            section_number=section_number
        )

        try:
            # Call OpenAI API with structured output
            request_params = {
                "model": self.analysis_model,
                "messages": [
                    {"role": "system", "content": self._get_document_analysis_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            }

            # Only add temperature for non-GPT-5 models
            if not self._uses_default_temperature_only(self.analysis_model):
                request_params["temperature"] = 0.7

            response = self.client.chat.completions.create(**request_params)

            # Extract content and parse JSON
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from OpenAI")

            import json
            result = json.loads(content)

            # Calculate cost and usage
            usage = response.usage
            cost_usd, _ = billing_service.calculate_token_cost(
                model=self.analysis_model,
                input_tokens=usage.prompt_tokens,
                cached_input_tokens=0,
                output_tokens=usage.completion_tokens
            )

            return {
                "summary": result.get("summary", ""),
                "questions": result.get("questions", []),
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost_usd": cost_usd
                }
            }

        except Exception as e:
            logger.error(f"Failed to analyze document section: {e}")
            raise

    def _get_document_analysis_system_prompt(self) -> str:
        """Get system prompt for document section analysis."""
        return """You are an expert business analyst specializing in requirements gathering.

Your task is to analyze requirements document sections and generate insightful interview questions.

For each section, you should:
1. Summarize the key requirements
2. Generate interview questions to clarify, validate, and explore the requirements
3. Categorize questions by type: clarification, validation, exploration, edge_case, constraint, priority
4. Determine importance: "must" for critical requirements, "should" for important but not critical
5. Provide expected answer elements that would make an answer sufficient
6. Suggest followup questions for insufficient answers

Your questions should:
- Be open-ended and encourage detailed responses
- Target ambiguities, assumptions, and missing information
- Uncover constraints, edge cases, and hidden requirements
- Help validate stakeholder understanding
- Be practical and actionable

Output format: JSON with structure:
{
  "summary": "Brief summary of key requirements in this section",
  "questions": [
    {
      "question_text": "The interview question",
      "question_type": "clarification|validation|exploration|edge_case|constraint|priority",
      "importance": "must|should",
      "expected_answer_elements": ["Element 1", "Element 2", ...],
      "suggested_followup": "Followup question if answer is insufficient",
      "coverage_rule": {
        "semantic_anchors": ["key", "phrases"],
        "expected_keywords": ["keyword1", "keyword2"],
        "must_mention_elements": [
          {"text": "Critical element", "required": true, "aliases": [], "subpoints": []}
        ],
        "thresholds": {
          "probably_sufficient": 0.65,
          "sufficient": 0.80
        }
      }
    }
  ]
}
"""

    def _build_document_analysis_prompt(
        self,
        section_text: str,
        section_title: Optional[str] = None,
        document_title: Optional[str] = None,
        section_number: int = 1
    ) -> str:
        """Build prompt for document section analysis."""
        title_info = f"Document: {document_title}\n" if document_title else ""
        section_info = f"Section {section_number}: {section_title}\n\n" if section_title else f"Section {section_number}\n\n"

        return f"""{title_info}{section_info}Content:
{section_text}

Please analyze this requirements section and generate interview questions to:
1. Clarify any ambiguous or unclear requirements
2. Validate understanding of the stated requirements
3. Explore edge cases, constraints, and hidden requirements
4. Determine priorities and importance

Generate 2-5 high-quality questions based on the content's complexity.
Focus on questions that will help write a comprehensive BRD (Business Requirements Document).

Return your analysis in JSON format as specified in the system prompt."""


openai_service = OpenAIService()
