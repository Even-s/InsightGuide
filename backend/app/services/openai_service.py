"""OpenAI API integration service for slide analysis and topic card generation."""

import json
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

    def classify_speaker(self, transcript: str) -> str:
        """
        Classify whether a transcript is from the interviewer or interviewee.
        Uses GPT-5.4-mini for accurate semantic classification.
        """
        try:
            from app.db.session import SessionLocal
            from app.services.prompt_registry_service import prompt_registry_service

            # Default fallback prompt
            system_prompt = (
                "判斷以下語句是「訪問者提問」還是「受訪者回答」。\n"
                "訪問者特徵：提出問題、請求描述/確認、使用疑問句、引導話題。\n"
                "受訪者特徵：描述現況、提供資訊、說明流程、回答問題、陳述事實。\n"
                "只回傳一個字：interviewer 或 interviewee"
            )

            # Try to load from registry
            db = SessionLocal()
            try:
                rendered = prompt_registry_service.render_prompt(
                    db,
                    "classify_speaker",
                    {"transcript": transcript[:200]}
                )
                if rendered and "system_prompt" in rendered:
                    system_prompt = rendered["system_prompt"]
            except Exception as e:
                logger.debug(f"Failed to load classify_speaker prompt from registry: {e}")
            finally:
                db.close()

            response = self.client.chat.completions.create(
                model="gpt-5.4-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript[:200]},
                ],
                temperature=0,
                max_completion_tokens=10,
            )
            result = response.choices[0].message.content.strip().lower()
            if "interviewer" in result:
                return "interviewer"
            return "interviewee"
        except Exception as e:
            logger.warning(f"Speaker classification failed: {e}")
            return "interviewee"

    def generate_interview_themes(
        self,
        document_title: str,
        full_text: str,
        sections: list,
        deck_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Phase 1: Analyze full BRD document and generate interview themes.

        Returns dict with interview_objective, themes[], priority_order, priority_reasoning.
        """
        logger.info(f"Generating interview themes for: {document_title}")

        section_list = "\n".join(
            f"- Section {s.section_number}: {s.title or '(untitled)'}"
            for s in sections
        )

        # Default fallback prompt
        system_prompt_fallback = """你是一位資深的商業分析師（BA），擅長從需求初稿中找出資訊缺口，並設計訪談策略。

你的任務是：分析整份 BRD 初稿，產出一份結構化的「訪談單元規劃」。

每個訪談單元代表一個需要在訪談中釐清的主題領域。你應該：
1. 找出初稿中的缺口、模糊處、假設、待確認事項
2. 將這些缺口整理成 8-13 個訪談單元（含開場與結尾）
3. 為每個單元寫出「提問依據」—— 說明為什麼需要問這個主題
4. 標註每個單元對應的 BRD 章節
5. 排出訪談優先順序
6. 避免逐段照抄原文標題，應以「訪談邏輯」重新組織

訪談單元的典型結構：
- 第 0 單元：訪談開場與範圍確認
- 中間單元：核心業務規則、使用者角色、流程、例外、資料需求等
- 最後一單元：訪談結尾確認（待補事項、假設條件、下一步）

輸出格式（JSON）：
{
  "interview_objective": "本次訪談的主要目標（1-2句）",
  "themes": [
    {
      "theme_number": 0,
      "title": "訪談開場與範圍確認",
      "rationale": "初版只定義需求方向...尚未明確第一階段範圍、是否採 MVP",
      "brd_mapping": ["需求背景", "需求範圍", "MVP 定義"],
      "priority": 3,
      "estimated_minutes": 5,
      "source_section_numbers": [1, 2]
    }
  ],
  "priority_order": [1, 3, 5, 6, 7],
  "priority_reasoning": "若訪談時間有限，建議優先..."
}

注意：
- theme_number 從 0 開始
- priority 越小越優先（1 = 最重要）
- priority_order 是 theme_number 的排列，表示建議的訪談順序
- source_section_numbers 指向原始文件的段落編號
- rationale 必須說明「為什麼要問」，不是「這段在講什麼」
- brd_mapping 應使用常見 BRD 章節名稱
"""

        system_prompt = system_prompt_fallback

        # Try to load from registry
        from app.db.session import SessionLocal
        from app.services.prompt_registry_service import prompt_registry_service

        db = SessionLocal()
        try:
            rendered = prompt_registry_service.render_prompt(
                db,
                "generate_interview_themes",
                {
                    "document_title": document_title,
                    "section_list": section_list,
                    "full_text": full_text[:12000]
                }
            )
            if rendered and "system_prompt" in rendered:
                system_prompt = rendered["system_prompt"]
        except Exception as e:
            logger.debug(f"Failed to load generate_interview_themes prompt from registry: {e}")
        finally:
            db.close()

        user_prompt = f"""文件標題：{document_title}

段落列表：
{section_list}

完整文件內容：
{full_text[:12000]}

請分析這份 BRD 初稿，產出訪談單元規劃。以 JSON 格式回傳。
"""

        try:
            model = "gpt-4o"
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                response_format={"type": "json_object"},
            )

            billing_service.record_deck_chat_completion(
                deck_id=deck_id,
                operation="generate_interview_themes",
                model=model,
                response=response,
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            logger.info(f"Generated {len(result.get('themes', []))} interview themes")
            return result

        except Exception as e:
            logger.error(f"Failed to generate interview themes: {e}")
            raise

    def generate_theme_question_cards(
        self,
        document_title: str,
        document_summary: str,
        theme_title: str,
        theme_rationale: str,
        theme_brd_mapping: list,
        source_sections_text: str,
        deck_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Phase 2: Generate question cards for a single interview theme.

        Returns dict with cards[].
        """
        logger.info(f"Generating question cards for theme: {theme_title}")

        # Default fallback prompt
        system_prompt_fallback = """你是一位資深商業分析師，負責為特定訪談單元設計「提問主題」與「建議提問」。

你的輸出結構是「主題 → 問題」的階層：
- 一個訪談單元下有 3-6 個提問主題（focus_text）
- 每個提問主題下有 1-3 個具體的建議提問（question_text）
- 同一個提問主題下的問題應循序漸進：先問大方向，再深入細節

每張卡片的欄位：
- focus_text：提問主題（這組問題要補齊什麼 BRD 資訊）。同一主題下的多張卡片 focus_text 必須完全相同。
- question_text：建議提問（訪談者可以怎麼問）
- question_type：問題類型
- importance：重要度（must = 必問, should = 選問）
- expected_answer_elements：期待回答要素
- suggested_followup：追問方向
- brd_mapping：對應 BRD 區塊
- coverage_rule：判斷回答是否充分的規則

設計語言：
- 以 BA 對 BU 訪談的語氣撰寫，語句要自然、清楚、可直接念出口。
- 避免使用「agent 的 agent」、「系統之系統」、「該功能模組」等技術或重複詞。若原文提到 agent，對 BU 的問法優先稱為「這個助手」、「需求訪談助手」或「這套工具」。
- focus_text 使用名詞化的資訊缺口，例如「確認需求訪談助手的目標與範圍」、「界定第一階段支援對象與不納入範圍」。
- question_text 使用訪談句型，例如「想先請你說明，這個助手第一階段主要希望解決的是什麼問題？」而不是「能否描述 agent 的主要目標？」。
- 若訪談單元與「目標與範圍」相關，必須明確區分：業務目標、第一階段範圍、使用對象、支援情境、不支援或延後處理的項目。
- suggested_followup 要能接在回答不足之後直接追問，不要只重述原問題。
- expected_answer_elements 與 must_mention_elements 要寫成可驗收的資訊項，而不是抽象詞。

目標與範圍類單元的推薦語言範例：
- focus_text: "確認需求訪談助手的業務目標"
- question_text: "想先請你說明，這個需求訪談助手第一階段最想解決的是什麼問題？"
- suggested_followup: "如果只能先做 MVP，哪些目標是這一階段一定要達成的？"
- focus_text: "界定第一階段支援範圍"
- question_text: "這個助手第一階段主要支援哪些需求訪談情境？哪些情境先不納入？"
- suggested_followup: "可以再補充不支援或延後處理的需求類型嗎？"

輸出格式（JSON）：
{
  "cards": [
    {
      "focus_text": "釐清服務優先級的判斷因素",
      "question_text": "BU 認為服務優先級最重要的判斷因素有哪些？",
      "question_type": "clarification",
      "importance": "must",
      "expected_answer_elements": ["主要排序因子", "因子優先順序"],
      "suggested_followup": "這些因素是由誰決定的？",
      "brd_mapping": ["排序規則", "商業規則"],
      "coverage_rule": {
        "semantic_anchors": ["服務優先級", "判斷因素"],
        "expected_keywords": ["KYC", "資產", "交易頻率"],
        "must_mention_elements": [
          {"text": "說明主要排序因子", "required": true, "aliases": [], "subpoints": []}
        ],
        "thresholds": {"probably_sufficient": 0.65, "sufficient": 0.80}
      }
    },
    {
      "focus_text": "釐清服務優先級的判斷因素",
      "question_text": "若 KYC、資產級距與交易頻率互相衝突，排序應以哪個為主？",
      "question_type": "clarification",
      "importance": "must",
      "expected_answer_elements": ["因子衝突時決策原則", "是否有權重"],
      "suggested_followup": "是否已有既定服務規則或過去人工排序邏輯可以提供？",
      "brd_mapping": ["排序規則"],
      "coverage_rule": {
        "semantic_anchors": ["衝突", "優先順序", "權重"],
        "expected_keywords": ["衝突", "優先", "權重", "規則"],
        "must_mention_elements": [
          {"text": "說明衝突時優先原則", "required": true, "aliases": ["以哪個為主"], "subpoints": []}
        ],
        "thresholds": {"probably_sufficient": 0.65, "sufficient": 0.80}
      }
    }
  ]
}

規則：
- 同一 focus_text 下的問題字串必須完全一致（系統用它來分組）
- 每個訪談單元產出 3-6 個提問主題，每個主題 1-3 個問題，總計 8-15 張卡片
- question_type: clarification, validation, exploration, edge_case, constraint, priority
- importance: must（核心缺口）或 should（補充資訊）
- focus_text 是系統判斷回答是否充分的核心
- 不得要求完整帳號、身分證字號等敏感個資
- cards 陣列的順序必須是「適合實際對話的提問順序」：先問全局性、背景性的問題，再問細節與規則，最後問確認與例外。模擬一位資深 BA 在訪談現場自然的對話節奏。
- 同一 focus_text 下的問題也要按由淺入深排列：先問開放式大問題，再問確認細節、邊界條件。
"""

        system_prompt = system_prompt_fallback

        # Try to load from registry
        from app.db.session import SessionLocal
        from app.services.prompt_registry_service import prompt_registry_service

        db = SessionLocal()
        try:
            rendered = prompt_registry_service.render_prompt(
                db,
                "generate_theme_question_cards",
                {
                    "document_title": document_title,
                    "document_summary": document_summary,
                    "theme_title": theme_title,
                    "theme_rationale": theme_rationale,
                    "theme_brd_mapping": ', '.join(theme_brd_mapping),
                    "source_sections_text": source_sections_text[:8000]
                }
            )
            if rendered and "system_prompt" in rendered:
                system_prompt = rendered["system_prompt"]
        except Exception as e:
            logger.debug(f"Failed to load generate_theme_question_cards prompt from registry: {e}")
        finally:
            db.close()

        user_prompt = f"""文件標題：{document_title}
文件摘要：{document_summary}

訪談單元：{theme_title}
提問依據：{theme_rationale}
對應 BRD 章節：{', '.join(theme_brd_mapping)}

來源段落內容：
{source_sections_text[:8000]}

請為這個訪談單元產生提問重點卡。以 JSON 格式回傳。
"""

        try:
            model = "gpt-4o"
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                response_format={"type": "json_object"},
            )

            billing_service.record_deck_chat_completion(
                deck_id=deck_id,
                operation="generate_theme_question_cards",
                model=model,
                response=response,
                source_id=f"theme:{theme_title}",
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            logger.info(f"Generated {len(result.get('cards', []))} cards for theme: {theme_title}")
            return result

        except Exception as e:
            logger.error(f"Failed to generate theme question cards: {e}")
            raise

    def _get_document_analysis_system_prompt(self) -> str:
        """Legacy: Get system prompt for per-section analysis (fallback only)."""
        return """你是一位資深商業分析師，擅長從需求文件中找出資訊缺口並設計訪談問題。

分析需求文件段落，產出訪談問題。每個問題代表一個 BRD 資訊缺口。

輸出格式（JSON）：
{
  "summary": "段落重點摘要",
  "questions": [
    {
      "question_text": "建議提問",
      "question_type": "clarification|validation|exploration|edge_case|constraint|priority",
      "importance": "must|should",
      "expected_answer_elements": ["期待回答要素1", "期待回答要素2"],
      "suggested_followup": "追問方向",
      "coverage_rule": {
        "semantic_anchors": ["語義錨點"],
        "expected_keywords": ["關鍵詞"],
        "must_mention_elements": [
          {"text": "必須回答的要素", "required": true, "aliases": [], "subpoints": []}
        ],
        "thresholds": {
          "probably_sufficient": 0.65,
          "sufficient": 0.80
        }
      }
    }
  ]
}

規則：
- 產生 3-5 個問題
- 問題要能幫助撰寫完整的 BRD
- 按對話順序排列（先背景，再細節，最後確認）
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
