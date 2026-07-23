"""Create isolated, ready-to-run interview demos without document analysis."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.interview_round import InterviewRound
from app.models.interview_round_slot import InterviewRoundSlot
from app.models.interview_series import InterviewSeries
from app.models.interview_session import InterviewCardState, InterviewSession
from app.models.interview_theme import InterviewTheme
from app.models.prep_session import PrepSession
from app.models.project import Project
from app.models.question_card import QuestionCard
from app.models.question_card_slot import QuestionCardSlot
from app.models.stakeholder_profile import StakeholderProfile
from app.models.stakeholder_profile_slot import StakeholderProfileSlot
from app.models.stakeholder_slot import StakeholderSlot
from app.services.project_service import project_service


class DemoTemplateNotFoundError(ValueError):
    """Raised when a requested public demo template does not exist."""


def _card(
    question: str,
    focus: str,
    elements: List[str],
    followup: str,
    brd_mapping: List[str],
    *,
    importance: str = "must",
) -> Dict[str, Any]:
    criteria = [
        {
            "id": f"criterion_{index}",
            "description": element,
            "type": "value_slot",
            "required": importance == "must" or index == 0,
            "critical": index == 0 and importance == "must",
            "weight": round(1 / len(elements), 3),
        }
        for index, element in enumerate(elements)
    ]
    return {
        "question": question,
        "focus": focus,
        "elements": elements,
        "followup": followup,
        "brd_mapping": brd_mapping,
        "importance": importance,
        "coverage_rule": {
            "semanticAnchors": elements,
            "expectedKeywords": elements,
            "mustMentionElements": [
                {"text": element, "required": importance == "must" or index == 0}
                for index, element in enumerate(elements)
            ],
            "negativeSignals": [],
            "thresholds": {"probablySufficient": 0.62, "sufficient": 0.78},
            "scoringWeights": {
                "semanticSimilarity": 0.55,
                "keywordCoverage": 0.25,
                "elementCoverage": 0.2,
            },
            "rubricVersion": "demo-v1",
            "answerTarget": "；".join(elements),
            "criteria": criteria,
        },
    }


DEMO_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "current-process": {
        "title": "現況流程探索",
        "description": "用具體案例走過目前流程、參與角色與例外處理。",
        "objective": "了解受訪者目前的端到端作業流程、角色分工與例外處理。",
        "themes": [
            {
                "title": "最近一次實際案例",
                "rationale": "用真實案例建立共同情境，避免只得到理想流程。",
                "brd_mapping": ["現況流程"],
                "cards": [
                    _card(
                        "請挑最近一次實際案例，當時是怎麼開始的？",
                        "觸發情境",
                        ["觸發事件", "案例背景"],
                        "當時是誰先提出需求或啟動作業？",
                        ["現況流程"],
                    ),
                    _card(
                        "從開始到完成，你依序做了哪些事情？",
                        "端到端步驟",
                        ["主要步驟", "先後順序", "完成條件"],
                        "哪一步完成後，下一個人才能接手？",
                        ["現況流程"],
                    ),
                ],
            },
            {
                "title": "角色與交接",
                "rationale": "釐清責任、資訊來源與跨角色交接。",
                "brd_mapping": ["利害關係人", "資料需求"],
                "cards": [
                    _card(
                        "過程中有哪些人或單位參與？各自負責什麼？",
                        "角色分工",
                        ["參與角色", "主要責任"],
                        "哪個責任最容易不清楚？",
                        ["利害關係人"],
                    ),
                    _card(
                        "交接時會傳遞哪些資訊或文件？",
                        "交接資訊",
                        ["交接時點", "資訊或文件", "接收方式"],
                        "你怎麼知道資訊已經完整送達？",
                        ["資料需求"],
                    ),
                ],
            },
            {
                "title": "例外與完成標準",
                "rationale": "找出流程分支與判定完成的實際規則。",
                "brd_mapping": ["業務規則", "例外流程"],
                "cards": [
                    _card(
                        "最常見的例外情況是什麼？你通常怎麼處理？",
                        "例外處理",
                        ["例外情況", "處理方式", "需要協助的角色"],
                        "如果處理失敗，下一步會怎麼做？",
                        ["例外流程"],
                    ),
                    _card(
                        "你如何判斷這次作業真的完成了？",
                        "完成條件",
                        ["完成標準", "確認方式"],
                        "是否還需要通知誰或留下紀錄？",
                        ["業務規則"],
                        importance="should",
                    ),
                ],
            },
        ],
    },
    "pain-and-needs": {
        "title": "痛點與需求探索",
        "description": "從真實困難、影響程度一路探索期待的改善結果。",
        "objective": "辨識高影響痛點、現有替代方案與可驗證的改善需求。",
        "themes": [
            {
                "title": "具體痛點",
                "rationale": "以近期事件確認問題實際如何發生。",
                "brd_mapping": ["問題陳述"],
                "cards": [
                    _card(
                        "最近一次讓你覺得最麻煩的情況是什麼？",
                        "痛點案例",
                        ["具體情境", "發生的問題"],
                        "當時原本想完成什麼？",
                        ["問題陳述"],
                    ),
                    _card(
                        "這個問題通常在哪個步驟發生？多久會遇到一次？",
                        "發生條件",
                        ["發生步驟", "發生頻率", "觸發條件"],
                        "哪些情況下特別容易發生？",
                        ["問題陳述"],
                    ),
                ],
            },
            {
                "title": "影響與替代做法",
                "rationale": "量化問題價值並理解使用者目前如何繞過限制。",
                "brd_mapping": ["效益目標", "現況限制"],
                "cards": [
                    _card(
                        "這個問題對時間、品質或其他人造成什麼影響？",
                        "問題影響",
                        ["影響對象", "影響類型", "影響程度"],
                        "可以用一個最近的數字或結果說明嗎？",
                        ["效益目標"],
                    ),
                    _card(
                        "現在你用什麼方式暫時解決或避開它？",
                        "替代方案",
                        ["目前做法", "做法限制"],
                        "這個做法最不理想的地方是什麼？",
                        ["現況限制"],
                    ),
                ],
            },
            {
                "title": "期待改善",
                "rationale": "把抱怨轉成結果導向且可驗收的需求。",
                "brd_mapping": ["需求", "驗收條件"],
                "cards": [
                    _card(
                        "如果這個問題被解決，理想上你希望事情怎麼進行？",
                        "目標狀態",
                        ["期待流程", "期待結果"],
                        "哪個改變對你最重要？",
                        ["需求"],
                    ),
                    _card(
                        "你會用什麼標準判斷改善真的有效？",
                        "成功標準",
                        ["衡量指標", "可接受標準"],
                        "多久後可以觀察到這個結果？",
                        ["驗收條件"],
                        importance="should",
                    ),
                ],
            },
        ],
    },
    "new-system": {
        "title": "新系統需求確認",
        "description": "確認使用者、核心功能、規則、例外與導入優先級。",
        "objective": "確認新系統的核心使用情境、功能邊界、業務規則與優先順序。",
        "themes": [
            {
                "title": "使用情境與目標",
                "rationale": "先確認誰在什麼情境下要達成什麼結果。",
                "brd_mapping": ["使用者需求", "專案目標"],
                "cards": [
                    _card(
                        "誰會最常使用這個系統？通常在什麼情境下使用？",
                        "主要使用者",
                        ["使用者角色", "使用情境"],
                        "還有哪些偶爾使用但很重要的角色？",
                        ["使用者需求"],
                    ),
                    _card(
                        "使用者進入系統後，最重要的是完成哪件事？",
                        "核心任務",
                        ["核心任務", "預期結果"],
                        "如果只能先做好一件事，會是哪一件？",
                        ["專案目標"],
                    ),
                ],
            },
            {
                "title": "功能與規則",
                "rationale": "把核心任務拆成可實作的功能與判斷規則。",
                "brd_mapping": ["功能需求", "業務規則"],
                "cards": [
                    _card(
                        "為了完成核心任務，系統必須提供哪些功能？",
                        "必要功能",
                        ["必要功能", "功能輸入", "功能輸出"],
                        "其中哪些功能現在完全沒有替代方案？",
                        ["功能需求"],
                    ),
                    _card(
                        "有哪些條件、權限或審核規則必須遵守？",
                        "業務規則",
                        ["判斷條件", "權限或審核", "規則結果"],
                        "規則不成立時，系統應該怎麼處理？",
                        ["業務規則"],
                    ),
                ],
            },
            {
                "title": "例外與優先級",
                "rationale": "明確處理失敗情境並切出可交付的第一版。",
                "brd_mapping": ["例外流程", "需求優先級"],
                "cards": [
                    _card(
                        "資料不完整、操作失敗或遇到特殊案件時，系統應該怎麼辦？",
                        "系統例外",
                        ["例外類型", "系統回應", "後續處理"],
                        "哪些例外一定需要人工介入？",
                        ["例外流程"],
                    ),
                    _card(
                        "第一版上線時，哪些能力是必須有，哪些可以晚一點？",
                        "版本範圍",
                        ["第一版必備", "可延後項目", "排序理由"],
                        "少了哪一項就無法開始使用？",
                        ["需求優先級"],
                    ),
                ],
            },
        ],
    },
}


class DemoSessionService:
    expiry_hours = 24

    def list_templates(self) -> List[Dict[str, Any]]:
        return [
            self._template_summary(template_id, data)
            for template_id, data in DEMO_TEMPLATES.items()
        ]

    def create_demo_session(self, db: Session, *, user_id: str, template_id: str) -> Dict[str, Any]:
        template = DEMO_TEMPLATES.get(template_id)
        if not template:
            raise DemoTemplateNotFoundError(template_id)

        now = datetime.utcnow()
        expires_at = now + timedelta(hours=self.expiry_hours)
        ids = {
            name: self._id(prefix)
            for name, prefix in {
                "project": "proj",
                "slot": "slot",
                "profile": "profile",
                "assignment": "sps",
                "series": "series",
                "round": "round",
                "round_slot": "irs",
                "document": "doc",
                "session": "session",
            }.items()
        }
        prep_id = ids["document"]

        try:
            expired_projects = (
                db.query(Project)
                .filter(
                    Project.user_id == user_id,
                    Project.mode == "demo",
                    Project.is_ephemeral.is_(True),
                    Project.expires_at <= now,
                )
                .all()
            )
            for expired_project in expired_projects:
                project_service.prepare_project_deletion(db, expired_project)

            project = Project(
                id=ids["project"],
                user_id=user_id,
                title=f"Demo｜{template['title']}",
                description=template["description"],
                brd_scope={"objective": template["objective"]},
                status="active",
                mode="demo",
                is_ephemeral=True,
                expires_at=expires_at,
                template_id=template_id,
                created_at=now,
                updated_at=now,
            )
            db.add(project)
            db.flush()

            slot = StakeholderSlot(
                id=ids["slot"],
                project_id=project.id,
                role_category="demo_participant",
                role_label="示範受訪者",
                rationale="快速 Demo 的預設受訪角色。",
                expected_contributions=["實際經驗", "需求與限制"],
                key_questions_to_cover=[
                    card["question"] for theme in template["themes"] for card in theme["cards"]
                ],
                priority="required",
                min_interviews=1,
                first_wave=True,
                status="assigned",
                order_index=0,
                source="demo_template",
                created_at=now,
                updated_at=now,
            )
            profile = StakeholderProfile(
                id=ids["profile"],
                project_id=project.id,
                name="示範受訪者",
                role_title="情境體驗者",
                department="Demo",
                stakeholder_type="demo_participant",
                expertise_tags=["實際作業經驗"],
                knowledge_boundaries=[],
                status="scheduled",
                created_at=now,
                updated_at=now,
            )
            db.add_all([slot, profile])
            db.flush()
            db.add(
                StakeholderProfileSlot(
                    id=ids["assignment"],
                    project_id=project.id,
                    profile_id=profile.id,
                    slot_id=slot.id,
                    is_primary=True,
                    fit_level="strong",
                    created_at=now,
                    updated_at=now,
                )
            )

            series = InterviewSeries(
                id=ids["series"],
                project_id=project.id,
                stakeholder_profile_id=profile.id,
                title=template["title"],
                topic_key=f"demo:{template_id}",
                status="active",
                created_at=now,
                updated_at=now,
            )
            db.add(series)
            db.flush()
            interview_round = InterviewRound(
                id=ids["round"],
                series_id=series.id,
                round_number=1,
                objective=template["objective"],
                generation_mode="demo_template",
                source_session_ids=[],
                focus_topics=[theme["title"] for theme in template["themes"]],
                exclude_completed_questions=True,
                status="scheduled",
                created_at=now,
                updated_at=now,
            )
            db.add(interview_round)
            db.flush()
            db.add(
                InterviewRoundSlot(
                    id=ids["round_slot"],
                    round_id=interview_round.id,
                    slot_id=slot.id,
                    created_at=now,
                )
            )

            document = Document(
                id=ids["document"],
                user_id=user_id,
                project_id=project.id,
                stakeholder_profile_id=profile.id,
                interview_round_id=interview_round.id,
                guide_version=1,
                is_frozen=True,
                title=f"{template['title']}訪談指南",
                source_file_url=f"demo-template://{template_id}",
                file_type="md",
                status="analyzed",
                interview_objective=template["objective"],
                interview_priority_order=[theme["title"] for theme in template["themes"]],
                interview_priority_reasoning="依公版 Demo 訪談節奏排序。",
                created_at=now,
                updated_at=now,
            )
            db.add(document)
            db.flush()
            interview_round.guide_document_id = document.id

            prep = PrepSession(
                id=prep_id,
                document_id=document.id,
                user_id=user_id,
                title=f"{template['title']} Demo",
                status="ready",
                created_at=now,
                updated_at=now,
            )
            db.add(prep)
            db.flush()

            card_ids: List[str] = []
            first_theme_id = None
            for theme_index, theme_data in enumerate(template["themes"]):
                theme_id = self._id("theme")
                first_theme_id = first_theme_id or theme_id
                theme = InterviewTheme(
                    id=theme_id,
                    document_id=document.id,
                    theme_number=theme_index + 1,
                    title=theme_data["title"],
                    rationale=theme_data["rationale"],
                    brd_mapping=theme_data["brd_mapping"],
                    priority=theme_index + 1,
                    estimated_minutes=3,
                    order_index=theme_index,
                    is_required=True,
                    is_enabled=True,
                    created_at=now,
                    updated_at=now,
                )
                db.add(theme)
                db.flush()
                for card_index, card_data in enumerate(theme_data["cards"]):
                    card_id = self._id("card")
                    card_ids.append(card_id)
                    card = QuestionCard(
                        id=card_id,
                        document_id=document.id,
                        interview_theme_id=theme.id,
                        focus_text=card_data["focus"],
                        question_text=card_data["question"],
                        question_type="exploration",
                        importance=card_data["importance"],
                        coverage_rule=card_data["coverage_rule"],
                        suggested_followup=card_data["followup"],
                        expected_answer_elements=card_data["elements"],
                        brd_mapping=card_data["brd_mapping"],
                        estimated_seconds=75,
                        order_index=card_index,
                        status="pending",
                        confidence=0,
                        created_by="system",
                        target_roles=["demo_participant"],
                        question_intent=card_data["focus"],
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(card)
                    db.flush()
                    db.add(
                        QuestionCardSlot(
                            id=self._id("qcs"),
                            question_card_id=card.id,
                            slot_id=slot.id,
                            created_at=now,
                        )
                    )

            session = InterviewSession(
                id=ids["session"],
                prep_session_id=prep.id,
                document_id=document.id,
                user_id=user_id,
                project_id=project.id,
                stakeholder_profile_id=profile.id,
                interview_round_id=interview_round.id,
                interview_objective=template["objective"],
                status="idle",
                current_theme_id=first_theme_id,
                paused_duration_seconds=0,
                created_at=now,
            )
            db.add(session)
            db.flush()
            db.add_all(
                [
                    InterviewCardState(
                        id=self._id("cardstate"),
                        session_id=session.id,
                        question_card_id=card_id,
                        status="pending",
                        activation_score=0,
                        completion_score=0,
                        created_at=now,
                        updated_at=now,
                    )
                    for card_id in card_ids
                ]
            )
            db.commit()
            db.refresh(session)
        except Exception:
            db.rollback()
            raise

        return {
            "templateId": template_id,
            "projectId": project.id,
            "stakeholderProfileId": profile.id,
            "prepSessionId": prep.id,
            "documentId": document.id,
            "sessionId": session.id,
            "expiresAt": expires_at,
            "interviewPath": f"/interview/session/{session.id}",
        }

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _template_summary(template_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": template_id,
            "title": data["title"],
            "description": data["description"],
            "estimatedMinutes": sum(theme.get("estimated_minutes", 3) for theme in data["themes"]),
            "themeCount": len(data["themes"]),
            "questionCount": sum(len(theme["cards"]) for theme in data["themes"]),
        }


demo_session_service = DemoSessionService()
