"""Stakeholder Card Generator Service.

Generates interview question cards for a specific stakeholder based on:
- Project scope and objectives
- Stakeholder expertise and role
- StakeholderSlot recommendations (if linked)
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.interview_theme import InterviewTheme
from app.models.prep_session import PrepSession
from app.models.project import Project
from app.models.question_card import QuestionCard
from app.models.stakeholder_profile import StakeholderProfile
from app.models.stakeholder_slot import StakeholderSlot
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)


class StakeholderCardGenerator:
    """Generate interview cards tailored to a specific stakeholder."""

    def generate_cards_for_stakeholder(
        self,
        db: Session,
        project_id: str,
        stakeholder_profile_id: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate question cards for a specific stakeholder.

        Args:
            options: Optional generation settings:
                - duration_minutes: Target interview duration (affects card count)
                - interview_purpose: Free text describing this interview's goal
                - focus_topics: Topics to prioritize
                - exclude_topics: Topics to avoid
                - interview_style: exploratory/structured/validation
                - target_card_count: Desired number of cards
                - must_cover_topics: List of mandatory topics
                - reference_questions: Example questions for style reference

        Returns:
            Dict with document_id, prep_session_id, themes, card_count, status
        """
        self._generation_options = options or {}

        # Get project and stakeholder
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        stakeholder = (
            db.query(StakeholderProfile)
            .filter(StakeholderProfile.id == stakeholder_profile_id)
            .first()
        )
        if not stakeholder:
            raise ValueError(f"Stakeholder {stakeholder_profile_id} not found")

        # Get slot info if linked
        slot = None
        if stakeholder.slot_id:
            slot = (
                db.query(StakeholderSlot).filter(StakeholderSlot.id == stakeholder.slot_id).first()
            )

        # Step 1: Get or create virtual document
        document = self._get_or_create_virtual_document(db, project, stakeholder)

        # Step 2: Get or create prep session
        prep_session = self._get_or_create_prep_session(db, document, project.user_id)

        # Step 2.5: Clean up any existing themes/cards (for regeneration)
        existing_cards = (
            db.query(QuestionCard).filter(QuestionCard.document_id == document.id).all()
        )
        existing_themes = (
            db.query(InterviewTheme).filter(InterviewTheme.document_id == document.id).all()
        )
        if existing_themes or existing_cards:
            for c in existing_cards:
                db.delete(c)
            for t in existing_themes:
                db.delete(t)
            db.flush()
            logger.info(
                f"Cleaned up {len(existing_themes)} themes and {len(existing_cards)} cards for regeneration"
            )

        # Step 3: Generate themes using AI
        themes_data = self._generate_themes(project, stakeholder, slot)

        # Step 4: Create InterviewTheme records
        themes = []
        for theme_data in themes_data:
            theme = InterviewTheme(
                id=f"theme_{uuid.uuid4().hex[:12]}",
                document_id=document.id,
                theme_number=theme_data["theme_number"],
                title=theme_data["title"],
                rationale=theme_data["rationale"],
                brd_mapping=theme_data.get("brd_mapping", []),
                priority=theme_data.get("priority", 99),
                estimated_minutes=theme_data.get("estimated_minutes", 5),
                order_index=theme_data["theme_number"],
                is_required=True,
                is_enabled=True,
            )
            db.add(theme)
            themes.append(theme)

        db.commit()

        # Step 5: Generate cards for each theme (with per-theme error handling)
        all_cards = []
        for theme in themes:
            try:
                cards_data = self._generate_cards_for_theme(project, stakeholder, slot, theme)
            except Exception as e:
                logger.warning(f"Card generation failed for theme '{theme.title}': {e}")
                cards_data = self._fallback_cards_for_theme(theme)

            for idx, card_data in enumerate(cards_data):
                card = QuestionCard(
                    id=f"qcard_{uuid.uuid4().hex[:12]}",
                    document_id=document.id,
                    interview_theme_id=theme.id,
                    focus_text=card_data.get("focus_text"),
                    question_text=card_data["question_text"],
                    question_type=card_data.get("question_type", "clarification"),
                    importance=card_data.get("importance", "should"),
                    coverage_rule=card_data.get("coverage_rule", self._default_coverage_rule()),
                    suggested_followup=card_data.get("suggested_followup"),
                    expected_answer_elements=card_data.get("expected_answer_elements", []),
                    brd_mapping=card_data.get("brd_mapping", []),
                    estimated_seconds=card_data.get("estimated_seconds", 90),
                    order_index=idx,
                    status="pending",
                    created_by="ai",
                    target_roles=[stakeholder.stakeholder_type],
                    expertise_required=stakeholder.expertise_tags,
                    question_intent=card_data.get("question_intent"),
                )
                db.add(card)
                all_cards.append(card)

        # Always mark as ready, even if some themes had fallback cards
        prep_session.status = "ready"
        document.status = "analyzed"

        db.commit()

        # Refresh to get all relationships
        db.refresh(document)
        db.refresh(prep_session)

        return {
            "document_id": document.id,
            "prep_session_id": prep_session.id,
            "themes": [
                {
                    "id": theme.id,
                    "theme_number": theme.theme_number,
                    "title": theme.title,
                    "rationale": theme.rationale,
                    "priority": theme.priority,
                    "estimated_minutes": theme.estimated_minutes,
                }
                for theme in themes
            ],
            "card_count": len(all_cards),
            "status": "ready",
        }

    def get_interview_guide_status(
        self, db: Session, project_id: str, stakeholder_profile_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get existing interview guide status for a stakeholder.

        Returns None if no guide exists yet.
        """
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return None

        stakeholder = (
            db.query(StakeholderProfile)
            .filter(StakeholderProfile.id == stakeholder_profile_id)
            .first()
        )
        if not stakeholder:
            return None

        # Look for existing virtual document
        document_title = f"{project.title} - {stakeholder.name} 訪談大綱"
        document = (
            db.query(Document)
            .filter(
                Document.project_id == project_id,
                Document.title == document_title,
                Document.source_file_url == "generated",
            )
            .first()
        )

        if not document:
            return None

        # Get prep session
        prep_session = db.query(PrepSession).filter(PrepSession.document_id == document.id).first()

        if not prep_session:
            return None

        # Get themes and cards
        themes = (
            db.query(InterviewTheme)
            .filter(InterviewTheme.document_id == document.id)
            .order_by(InterviewTheme.order_index)
            .all()
        )

        cards = db.query(QuestionCard).filter(QuestionCard.document_id == document.id).all()

        return {
            "document_id": document.id,
            "prep_session_id": prep_session.id,
            "themes": [
                {
                    "id": theme.id,
                    "theme_number": theme.theme_number,
                    "title": theme.title,
                    "card_count": len([c for c in cards if c.interview_theme_id == theme.id]),
                }
                for theme in themes
            ],
            "card_count": len(cards),
            "status": prep_session.status,
        }

    def _get_or_create_virtual_document(
        self, db: Session, project: Project, stakeholder: StakeholderProfile
    ) -> Document:
        """Get or create a virtual document for the stakeholder."""
        document_title = f"{project.title} - {stakeholder.name} 訪談大綱"

        # Check if already exists
        existing = (
            db.query(Document)
            .filter(
                Document.project_id == project.id,
                Document.title == document_title,
                Document.source_file_url == "generated",
            )
            .first()
        )

        if existing:
            return existing

        # Create new virtual document
        document = Document(
            id=f"doc_{uuid.uuid4().hex[:12]}",
            user_id=project.user_id,
            project_id=project.id,
            title=document_title,
            source_file_url="generated",
            file_type="generated",
            status="analyzing",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        return document

    def _get_or_create_prep_session(
        self, db: Session, document: Document, user_id: str
    ) -> PrepSession:
        """Get or create prep session for the document."""
        # Check if already exists
        existing = db.query(PrepSession).filter(PrepSession.document_id == document.id).first()

        if existing:
            return existing

        # Create new prep session
        prep_session = PrepSession(
            id=f"prep_{uuid.uuid4().hex[:12]}",
            document_id=document.id,
            user_id=user_id,
            title=document.title,
            status="preparing",
        )
        db.add(prep_session)
        db.commit()
        db.refresh(prep_session)

        return prep_session

    def _generate_themes(
        self, project: Project, stakeholder: StakeholderProfile, slot: Optional[StakeholderSlot]
    ) -> List[Dict[str, Any]]:
        """Use AI to generate interview themes for this stakeholder."""
        brd_scope = project.brd_scope or {}

        # Build context
        context_parts = [
            f"專案名稱：{project.title}",
            f"專案描述：{project.description or '無'}",
        ]

        if brd_scope.get("business_domain"):
            context_parts.append(f"業務領域：{brd_scope['business_domain']}")

        if brd_scope.get("key_objectives"):
            objectives = "\n".join(f"- {obj}" for obj in brd_scope["key_objectives"])
            context_parts.append(f"主要目標：\n{objectives}")

        if brd_scope.get("out_of_scope"):
            out_of_scope = "\n".join(f"- {item}" for item in brd_scope["out_of_scope"])
            context_parts.append(f"不在範圍內：\n{out_of_scope}")

        context_parts.extend(
            [
                f"\n受訪者：{stakeholder.name}",
                f"職稱：{stakeholder.role_title or '未提供'}",
                f"角色類型：{stakeholder.stakeholder_type}",
            ]
        )

        if stakeholder.expertise_tags:
            context_parts.append(f"專長領域：{', '.join(stakeholder.expertise_tags)}")

        if stakeholder.knowledge_boundaries:
            context_parts.append(f"知識範圍：{', '.join(stakeholder.knowledge_boundaries)}")

        if slot:
            if slot.expected_contributions:
                contributions = "\n".join(f"- {c}" for c in slot.expected_contributions)
                context_parts.append(f"預期提供資訊：\n{contributions}")

            if slot.key_questions_to_cover:
                questions = "\n".join(f"- {q}" for q in slot.key_questions_to_cover)
                context_parts.append(f"建議關鍵問題：\n{questions}")

        context = "\n".join(context_parts)

        # Inject generation options into context
        opts = self._generation_options
        options_parts = []
        if opts.get("duration_minutes"):
            options_parts.append(f"預計訪談時長：{opts['duration_minutes']} 分鐘")
        if opts.get("interview_purpose"):
            options_parts.append(f"本次訪談目的：{opts['interview_purpose']}")
        if opts.get("focus_topics"):
            options_parts.append(f"聚焦主題：{opts['focus_topics']}")
        if opts.get("exclude_topics"):
            options_parts.append(f"排除主題（不要問）：{opts['exclude_topics']}")
        if opts.get("interview_style"):
            style_label = {
                "exploratory": "探索型（開放、廣泛）",
                "structured": "結構化（精確、逐項確認）",
                "validation": "驗證型（確認已知假設）",
            }.get(opts["interview_style"], opts["interview_style"])
            options_parts.append(f"訪談風格：{style_label}")
        if opts.get("must_cover_topics"):
            options_parts.append(f"必須涵蓋的主題：{', '.join(opts['must_cover_topics'])}")
        if opts.get("reference_questions"):
            options_parts.append(
                f"參考問題風格：\n" + "\n".join(f"- {q}" for q in opts["reference_questions"])
            )

        if options_parts:
            context += "\n\n## 訪談設定\n" + "\n".join(options_parts)

        # Determine target theme count based on duration
        duration = opts.get("duration_minutes", 30)
        if duration <= 15:
            theme_count_hint = "3-4"
        elif duration <= 30:
            theme_count_hint = "5-6"
        elif duration <= 45:
            theme_count_hint = "6-8"
        else:
            theme_count_hint = "7-10"

        # Call AI
        try:
            import json

            system_prompt = f"""你是訪談規劃專家。根據專案資訊和受訪者角色，產生結構化的訪談主題。

產生 {theme_count_hint} 個訪談主題。總時長控制在 {duration} 分鐘內。

嚴格規則：
- 每個主題都必須是「需要從受訪者口中得到具體資訊」的主題
- 不要產生「開場」「範圍確認」「結尾」等訪談技巧類主題 — 這些由系統自動處理
- 主題應該對應可寫入 BRD 的具體內容區塊（流程、痛點、需求、限制等）

每個主題包含：
- theme_number: 主題編號（從 0 開始）
- title: 主題標題（具體描述要了解什麼）
- rationale: 為什麼需要問這個主題（針對此受訪者）
- brd_mapping: 對應的 BRD 章節名稱
- priority: 重要度（1-3，越小越重要）
- estimated_minutes: 估計訪談時間（分鐘）

如果使用者指定了訪談目的或聚焦主題，請據此調整主題方向和深度。
如果使用者指定了排除主題，這些方向的主題不要出現。

輸出 JSON 格式：
{{
  "themes": [
    {{
      "theme_number": 0,
      "title": "現有資料處理流程與步驟",
      "rationale": "釐清目前整個流程如何運作",
      "brd_mapping": ["業務流程", "現況描述"],
      "priority": 1,
      "estimated_minutes": 8
    }}
  ]
}}"""

            user_prompt = f"""{context}

請為這位受訪者設計訪談主題。以 JSON 格式回傳。"""

            response = openai_service.client.chat.completions.create(
                model="gpt-5.4-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_completion_tokens=2000,
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(content)
            themes = result.get("themes", [])

            if themes:
                logger.info(f"Generated {len(themes)} themes for stakeholder {stakeholder.name}")
                return themes

        except Exception as e:
            logger.warning(f"AI theme generation failed, using defaults: {e}")

        # Fallback to default themes
        return self._default_themes(stakeholder, slot)

    def _default_themes(
        self, stakeholder: StakeholderProfile, slot: Optional[StakeholderSlot]
    ) -> List[Dict[str, Any]]:
        """Fallback themes if AI generation fails."""
        return [
            {
                "theme_number": 0,
                "title": "訪談開場與範圍確認",
                "rationale": f"確認 {stakeholder.name} 的工作範圍與本次訪談重點",
                "brd_mapping": ["專案背景", "訪談範圍"],
                "priority": 2,
                "estimated_minutes": 5,
            },
            {
                "theme_number": 1,
                "title": f"{stakeholder.stakeholder_type} 角色與職責",
                "rationale": f"了解 {stakeholder.name} 在此專案中的角色定位",
                "brd_mapping": ["角色定義", "職責範圍"],
                "priority": 1,
                "estimated_minutes": 10,
            },
            {
                "theme_number": 2,
                "title": "現況與痛點",
                "rationale": "了解目前的工作流程與遇到的問題",
                "brd_mapping": ["現況分析", "問題定義"],
                "priority": 1,
                "estimated_minutes": 15,
            },
            {
                "theme_number": 3,
                "title": "需求與期望",
                "rationale": "確認對新系統的需求與期望",
                "brd_mapping": ["需求定義", "功能需求"],
                "priority": 1,
                "estimated_minutes": 15,
            },
            {
                "theme_number": 4,
                "title": "訪談結尾確認",
                "rationale": "確認是否有遺漏的重點，以及下一步",
                "brd_mapping": ["待補事項", "下一步"],
                "priority": 3,
                "estimated_minutes": 5,
            },
        ]

    def _generate_cards_for_theme(
        self,
        project: Project,
        stakeholder: StakeholderProfile,
        slot: Optional[StakeholderSlot],
        theme: InterviewTheme,
    ) -> List[Dict[str, Any]]:
        """Generate question cards for a specific theme."""
        brd_scope = project.brd_scope or {}

        context = f"""專案：{project.title}
受訪者：{stakeholder.name} ({stakeholder.stakeholder_type})
主題：{theme.title}
主題說明：{theme.rationale}"""

        try:
            import json

            system_prompt = """你是訪談規劃專家。為特定訪談主題設計具體的訪談問題。

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
  好：「目前這些資料是怎麼進到你們的系統裡的？」
  壞：「Lydia 想先請教您，您在這個流程裡實際會參與到哪些環節？」
- 每個問題只問一件事

每個問題包含：
- focus_text: 提問重點（一句話描述要釐清什麼）
- question_text: 具體問題（口語化，可直接開口問）
- question_type: clarification/validation/exploration/edge_case/constraint/priority
- importance: must（必問）或 should（選問）
- expected_answer_elements: 期待的回答要素（字串陣列）
- suggested_followup: 如果回答不夠深入，追問什麼
- brd_mapping: 對應的 BRD 章節
- coverage_rule: 判斷回答充分性的規則
- estimated_seconds: 估計回答時間（秒）

輸出 JSON：
{
  "cards": [
    {
      "focus_text": "資料來源如何進入處理流程",
      "question_text": "目前這些客戶資料通常是怎麼進到你們的作業流程裡的？",
      "question_type": "clarification",
      "importance": "must",
      "expected_answer_elements": ["資料來源", "進入方式", "觸發時機"],
      "suggested_followup": "有沒有哪些來源的處理方式跟其他不一樣？",
      "brd_mapping": ["資料來源", "輸入流程"],
      "coverage_rule": {
        "semantic_anchors": ["資料來源", "進入流程", "匯入方式"],
        "expected_keywords": ["來源", "匯入", "下載", "收到"],
        "must_mention_elements": [
          {"text": "資料如何進入", "required": true, "aliases": ["怎麼收到", "匯入方式"], "subpoints": []}
        ],
        "thresholds": {"probably_sufficient": 0.65, "sufficient": 0.80}
      },
      "estimated_seconds": 90
    }
  ]
}

請產生 3-5 個問題，按訪談自然順序排列。"""

            user_prompt = f"""{context}

請為這個主題設計訪談問題。以 JSON 格式回傳。"""

            response = openai_service.client.chat.completions.create(
                model="gpt-5.4-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_completion_tokens=2000,
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(content)
            cards = result.get("cards", [])

            if cards:
                logger.info(f"Generated {len(cards)} cards for theme {theme.title}")
                return cards

        except Exception as e:
            logger.warning(f"AI card generation failed, using defaults: {e}")

        # Fallback
        return self._default_cards_for_theme(theme)

    def _default_cards_for_theme(self, theme: InterviewTheme) -> List[Dict[str, Any]]:
        """Fallback cards if AI generation fails."""
        return [
            {
                "focus_text": f"了解 {theme.title} 的背景",
                "question_text": f"可以請您說明一下 {theme.title} 的現況嗎？",
                "question_type": "exploration",
                "importance": "must",
                "expected_answer_elements": ["現況描述", "背景說明"],
                "suggested_followup": "您認為目前最大的挑戰是什麼？",
                "brd_mapping": theme.brd_mapping or ["一般資訊"],
                "coverage_rule": self._default_coverage_rule(),
                "estimated_seconds": 120,
            },
            {
                "focus_text": f"釐清 {theme.title} 的需求",
                "question_text": f"關於 {theme.title}，您有什麼具體的需求或期望？",
                "question_type": "clarification",
                "importance": "should",
                "expected_answer_elements": ["具體需求", "期望"],
                "suggested_followup": "可以舉個例子說明嗎？",
                "brd_mapping": theme.brd_mapping or ["需求定義"],
                "coverage_rule": self._default_coverage_rule(),
                "estimated_seconds": 120,
            },
        ]

    def _fallback_cards_for_theme(self, theme) -> List[Dict[str, Any]]:
        """Generate minimal fallback cards when AI fails for a theme."""
        return [
            {
                "question_text": f"關於「{theme.title}」，請問目前的現況是什麼？",
                "question_type": "exploration",
                "importance": "must",
                "focus_text": theme.title,
                "suggested_followup": "可以再詳細說明嗎？",
                "expected_answer_elements": [],
                "estimated_seconds": 120,
            },
            {
                "question_text": f"在「{theme.title}」方面，最大的痛點或挑戰是什麼？",
                "question_type": "exploration",
                "importance": "must",
                "focus_text": f"{theme.title} - 痛點",
                "suggested_followup": "這個問題多久發生一次？影響有多大？",
                "expected_answer_elements": [],
                "estimated_seconds": 120,
            },
            {
                "question_text": f"對於「{theme.title}」，你期望新系統能怎麼改善？",
                "question_type": "exploration",
                "importance": "should",
                "focus_text": f"{theme.title} - 期望",
                "suggested_followup": "有沒有具體的使用情境？",
                "expected_answer_elements": [],
                "estimated_seconds": 90,
            },
        ]

    def _default_coverage_rule(self) -> Dict[str, Any]:
        """Default coverage rule structure."""
        return {
            "semantic_anchors": ["說明", "描述", "解釋"],
            "expected_keywords": ["說明", "描述"],
            "must_mention_elements": [
                {
                    "text": "提供說明",
                    "required": True,
                    "aliases": ["回答", "說明"],
                    "subpoints": [],
                }
            ],
            "thresholds": {
                "probably_sufficient": 0.60,
                "sufficient": 0.75,
            },
        }


stakeholder_card_generator = StakeholderCardGenerator()
