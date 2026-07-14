"""OpenAI API integration service for document analysis and topic card generation."""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import openai
from openai import OpenAI
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.billing_service import billing_service

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI APIs."""

    def __init__(self):
        """Initialize OpenAI client."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=60.0)
        self.analysis_model = settings.DOCUMENT_ANALYSIS_MODEL

    @retry(
        retry=retry_if_exception_type(
            (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.InternalServerError,
            )
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
    )
    def chat_completion(
        self,
        messages: list,
        *,
        model: str = "gpt-4o-mini",
        temperature: float = 0,
        response_format: Optional[dict] = None,
        max_tokens: Optional[int] = None,
        # Billing context (optional — if provided, records cost)
        db: Optional[Session] = None,
        session_id: Optional[str] = None,
        document_id: Optional[str] = None,
        purpose: str = "general",
    ) -> Any:
        """Centralized chat completion with billing, retry, timeout, and logging.

        Returns the parsed response message content (as dict if JSON, else str).
        """
        start_time = time.time()

        # Build request parameters
        request_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if response_format is not None:
            request_params["response_format"] = response_format

        if max_tokens is not None:
            if self._requires_max_completion_tokens(model):
                request_params["max_completion_tokens"] = max_tokens
            else:
                request_params["max_tokens"] = max_tokens

        # Call OpenAI API
        response = self.client.chat.completions.create(**request_params)

        # Extract usage
        usage = response.usage
        total_tokens = usage.total_tokens if usage else 0
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        # Calculate elapsed time
        elapsed_ms = (time.time() - start_time) * 1000

        # Log timing and usage
        logger.info(f"[AI] {purpose}: {elapsed_ms:.0f}ms, model={model}, tokens={total_tokens}")

        # Log slow calls
        if elapsed_ms > 5000:
            logger.warning(
                f"[AI] Slow call detected: {purpose} took {elapsed_ms:.0f}ms with {total_tokens} tokens"
            )

        # Record billing if db provided
        if db is not None:
            try:
                cost_usd, pricing = billing_service.calculate_token_cost(
                    model=model,
                    input_tokens=input_tokens,
                    cached_input_tokens=0,
                    output_tokens=output_tokens,
                )

                # Create usage event
                import uuid
                from datetime import datetime

                from app.models.ai_usage_event import AIUsageEvent

                event = AIUsageEvent(
                    id=f"aiusage_{uuid.uuid4().hex[:12]}",
                    interview_session_id=session_id,
                    document_id=document_id,
                    operation=purpose,
                    model=model,
                    input_tokens=input_tokens,
                    cached_input_tokens=0,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    audio_seconds=0,
                    cost_usd=cost_usd,
                    pricing=pricing,
                    created_at=datetime.utcnow(),
                )
                db.add(event)
                db.commit()
            except Exception as e:
                logger.error(f"Failed to record billing for {purpose}: {e}")
                db.rollback()

        # Parse and return response
        content = response.choices[0].message.content
        if not content:
            logger.warning(f"Empty response from OpenAI for {purpose}")
            return ""

        # If JSON response format, try to parse
        if response_format and response_format.get("type") in ("json_object", "json_schema"):
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON response for {purpose}: {e}. Returning raw string."
                )
                return content

        return content

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
                        "content": "You are an expert at analyzing interview content and generating structured metadata for topic cards. Always respond with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
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

    def _requires_max_completion_tokens(self, model: str) -> bool:
        """Return True for models that use max_completion_tokens instead of max_tokens."""
        return model.startswith("gpt-5") or model.startswith("o")

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
            section_number=section_number,
        )

        try:
            # Call OpenAI API with structured output
            request_params = {
                "model": self.analysis_model,
                "messages": [
                    {"role": "system", "content": self._get_document_analysis_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
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
                output_tokens=usage.completion_tokens,
            )

            return {
                "summary": result.get("summary", ""),
                "questions": result.get("questions", []),
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost_usd": cost_usd,
                },
            }

        except Exception as e:
            logger.error(f"Failed to analyze document section: {e}")
            raise

    def generate_interview_themes(
        self,
        document_title: str,
        full_text: str,
        sections: list,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Phase 1: Analyze full BRD document and generate interview themes.

        Returns dict with interview_objective, themes[], priority_order, priority_reasoning.
        """
        logger.info(f"Generating interview themes for: {document_title}")

        section_list = "\n".join(
            f"- Section {s.section_number}: {s.title or '(untitled)'}" for s in sections
        )

        # Default fallback prompt
        system_prompt_fallback = """你是一位資深的商業分析師（BA），擅長從需求初稿中找出資訊缺口，並設計訪談策略。

你的任務是：分析整份 BRD 初稿，產出一份結構化的「訪談單元規劃」。

每個訪談單元代表一個需要在訪談中釐清的主題領域。你應該：
1. 找出初稿中的缺口、模糊處、假設、待確認事項
2. 將這些缺口整理成 5-8 個訪談單元
3. 為每個單元寫出「提問依據」—— 說明為什麼需要問這個主題
4. 標註每個單元對應的 BRD 章節
5. 排出訪談優先順序
6. 避免逐段照抄原文標題，應以「訪談邏輯」重新組織

嚴格規則：
- 不要產生「訪談開場」「範圍確認」「結尾確認」等訪談技巧類主題 — 這些由系統自動處理
- 每個主題都必須是「需要從受訪者口中得到具體資訊」的主題
- 主題應該對應可寫入 BRD 的具體內容區塊（流程、痛點、需求、限制等）

輸出格式（JSON）：
{
  "interview_objective": "本次訪談的主要目標（1-2句）",
  "themes": [
    {
      "theme_number": 0,
      "title": "現有業務流程與角色分工",
      "rationale": "初版未描述現有流程細節，需釐清目前的運作方式",
      "brd_mapping": ["業務流程", "角色權責"],
      "priority": 1,
      "estimated_minutes": 8,
      "source_section_numbers": [1, 2]
    }
  ],
  "priority_order": [0, 2, 3, 1],
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
                document_id=document_id,
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
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Phase 2: Generate question cards for a single interview theme.

        Returns dict with cards[].
        """
        logger.info(f"Generating question cards for theme: {theme_title}")

        # Default fallback prompt
        system_prompt_fallback = """你是一位資深商業分析師，負責為特定訪談單元設計具體的訪談問題。

嚴格規則：
- 每個問題必須是「需要受訪者提供具體資訊」的問題
- 不要產生以下類型的問題：
  • 開場白（「您好，我想先請教...」）
  • 範圍確認（「這樣的範圍合適嗎？」）
  • 結尾確認（「還有什麼想補充的嗎？」）
  • 引導語（「接下來我們聊聊...」）
  • 純禮貌句
- 問題中不要包含受訪者的名字
- 問題要直接切入主題，不需要前導語
- 每個問題只問一件事

每張卡片的欄位：
- focus_text：提問重點（這個問題要補齊什麼 BRD 資訊）
- question_text：具體問題（口語化，可直接開口問）
- question_type：問題類型
- importance：重要度（must = 必問, should = 選問）
- expected_answer_elements：期待回答要素
- suggested_followup：追問方向（接在回答不足之後直接追問）
- brd_mapping：對應 BRD 區塊
- coverage_rule：判斷回答是否充分的規則

設計語言：
- 以 BA 對 BU 訪談的語氣撰寫，語句要自然、清楚、可直接念出口。
- 避免使用「agent 的 agent」、「系統之系統」、「該功能模組」等技術或重複詞。
- question_text 使用訪談句型，例如「目前這些資料通常是怎麼進到你們的作業流程裡的？」
- expected_answer_elements 要寫成可驗收的資訊項，而不是抽象詞。

輸出格式（JSON）：
{
  "cards": [
    {
      "focus_text": "釐清服務優先級的判斷因素",
      "question_text": "你們判斷服務優先級最重要的因素有哪些？",
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
    }
  ]
}

規則：
- 每個訪談單元產出 2-4 張卡片，只保留最關鍵的問題
- question_type: clarification, validation, exploration, edge_case, constraint, priority
- importance: must（核心缺口）或 should（補充資訊）
- 不得要求完整帳號、身分證字號等敏感個資
- cards 陣列的順序必須是「適合實際對話的提問順序」：先問全局性、背景性的問題，再問細節與規則，最後問確認與例外。
"""

        system_prompt = system_prompt_fallback

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
                document_id=document_id,
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
        section_number: int = 1,
    ) -> str:
        """Build prompt for document section analysis."""
        title_info = f"Document: {document_title}\n" if document_title else ""
        section_info = (
            f"Section {section_number}: {section_title}\n\n"
            if section_title
            else f"Section {section_number}\n\n"
        )

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

    def audio_transcription(
        self,
        audio_bytes: bytes,
        model: str = "gpt-4o-transcribe",
        response_format: str = "verbose_json",
        timestamp_granularities: Optional[List[str]] = None,
        db: Optional[Session] = None,
        session_id: Optional[str] = None,
        document_id: Optional[str] = None,
        purpose: str = "diarization",
    ) -> Any:
        """Centralized audio transcription with billing and retry logic.

        Args:
            audio_bytes: Raw audio file bytes
            model: Transcription model (default: gpt-4o-transcribe)
            response_format: Response format (default: verbose_json for diarization)
            timestamp_granularities: Granularities for timestamps (default: ["segment"])
            db: Database session for billing (optional)
            session_id: Interview session ID for billing
            document_id: Document ID for billing
            purpose: Operation purpose for logging (default: diarization)

        Returns:
            Transcription response object with segments
        """
        import io

        start_time = time.time()

        # Build request parameters
        request_params = {
            "model": model,
            "file": ("audio.webm", io.BytesIO(audio_bytes), "audio/webm"),
            "response_format": response_format,
        }

        if timestamp_granularities:
            request_params["timestamp_granularities"] = timestamp_granularities
        else:
            request_params["timestamp_granularities"] = ["segment"]

        try:
            # Call OpenAI audio transcription API
            response = self.client.audio.transcriptions.create(**request_params)

            # Calculate elapsed time
            elapsed_ms = (time.time() - start_time) * 1000

            # Estimate audio duration from file size (rough estimate: ~1 minute per 100KB)
            audio_duration_seconds = max(1, len(audio_bytes) // 100000)

            # Log timing
            logger.info(
                f"[AUDIO] {purpose}: {elapsed_ms:.0f}ms, "
                f"model={model}, estimated_duration={audio_duration_seconds}s"
            )

            # Record billing if db provided
            if db is not None and session_id:
                try:
                    cost_usd, pricing = billing_service.calculate_token_cost(
                        model=model,
                        input_tokens=0,
                        cached_input_tokens=0,
                        output_tokens=0,
                    )

                    # Create usage event with audio_seconds
                    import uuid
                    from datetime import datetime

                    from app.models.ai_usage_event import AIUsageEvent

                    event = AIUsageEvent(
                        id=f"aiusage_{uuid.uuid4().hex[:12]}",
                        interview_session_id=session_id,
                        document_id=document_id,
                        operation=purpose,
                        model=model,
                        input_tokens=0,
                        cached_input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        audio_seconds=audio_duration_seconds,
                        cost_usd=cost_usd,
                        pricing=pricing,
                        created_at=datetime.utcnow(),
                    )
                    db.add(event)
                    db.commit()
                    logger.info(
                        f"Recorded audio transcription usage: {audio_duration_seconds}s, cost=${cost_usd}"
                    )
                except Exception as e:
                    logger.error(f"Failed to record billing for {purpose}: {e}")
                    db.rollback()

            return response

        except openai.RateLimitError as e:
            logger.error(f"Rate limit error in audio transcription: {e}")
            raise
        except openai.APIConnectionError as e:
            logger.error(f"API connection error in audio transcription: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in audio transcription: {e}")
            raise


openai_service = OpenAIService()
