"""Stakeholder Plan service — dynamic interview planning engine."""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.interview_session import InterviewSession
from app.models.project import Project
from app.models.stakeholder_profile import StakeholderProfile
from app.models.stakeholder_profile_slot import StakeholderProfileSlot
from app.models.stakeholder_slot import StakeholderSlot
from app.utils.chinese import to_traditional_zh

logger = logging.getLogger(__name__)

EXCLUSIVE_RATIONALE_PREFIX = re.compile(
    r"^(?:只有|唯有)(?:這個角色|這位受訪者|該角色|他們|她們|他|她)"
    r"能(?:夠)?(?:直接)?(?:說明|說出|說清楚|提供|釐清|確認|分享|回答)?"
)


class StakeholderSlotHasProfilesError(ValueError):
    """Raised when trying to delete a role slot that still has assigned participants."""


class StakeholderProfileSlotNotFoundError(ValueError):
    """Raised when assigning a profile to a missing slot."""


ROLE_CATEGORIES = [
    "business",
    "product",
    "engineering",
    "management",
    "operations",
    "customer_support",
    "legal",
    "finance",
    "design",
    "qa",
    "user",
    "other",
]

STAKEHOLDER_PLAN_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "stakeholder_interview_plan",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "slots": {
                    "type": "array",
                    "minItems": 2,
                    "items": {
                        "type": "object",
                        "properties": {
                            "role_category": {"type": "string", "enum": ROLE_CATEGORIES},
                            "role_label": {"type": "string"},
                            "rationale": {"type": "string"},
                            "expected_contributions": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "key_questions_to_cover": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["required", "recommended", "optional"],
                            },
                            "min_interviews": {"type": "integer", "minimum": 1},
                            "conditions": {"type": "string"},
                            "first_wave": {"type": "boolean"},
                        },
                        "required": [
                            "role_category",
                            "role_label",
                            "rationale",
                            "expected_contributions",
                            "key_questions_to_cover",
                            "priority",
                            "min_interviews",
                            "conditions",
                            "first_wave",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["slots"],
            "additionalProperties": False,
        },
    },
}

STAKEHOLDER_SLOT_DRAFT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "stakeholder_slot_draft",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "role_category": {"type": "string", "enum": ROLE_CATEGORIES},
                "role_label": {"type": "string"},
                "rationale": {"type": "string"},
                "expected_contributions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "key_questions_to_cover": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "priority": {
                    "type": "string",
                    "enum": ["required", "recommended", "optional"],
                },
                "min_interviews": {"type": "integer", "minimum": 1, "maximum": 20},
                "first_wave": {"type": "boolean"},
            },
            "required": [
                "role_category",
                "role_label",
                "rationale",
                "expected_contributions",
                "key_questions_to_cover",
                "priority",
                "min_interviews",
                "first_wave",
            ],
            "additionalProperties": False,
        },
    },
}

STAKEHOLDER_PROFILE_DRAFT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "stakeholder_profile_draft",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "role_title": {"type": "string"},
                "department": {"type": "string"},
                "stakeholder_type": {"type": "string", "enum": ROLE_CATEGORIES},
                "expertise_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "knowledge_boundaries": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": [
                "name",
                "role_title",
                "department",
                "stakeholder_type",
                "expertise_tags",
                "knowledge_boundaries",
            ],
            "additionalProperties": False,
        },
    },
}

INTERVIEW_GUIDE_DRAFT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "interview_guide_draft",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "duration_minutes": {"type": "integer", "minimum": 10, "maximum": 90},
                "interview_purpose": {"type": "string"},
                "focus_topics": {"type": "string"},
                "exclude_topics": {"type": "string"},
                "interview_style": {
                    "type": "string",
                    "enum": ["exploratory", "structured", "validation", ""],
                },
                "changed_fields": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "duration_minutes",
                            "interview_purpose",
                            "focus_topics",
                            "exclude_topics",
                            "interview_style",
                        ],
                    },
                },
            },
            "required": [
                "duration_minutes",
                "interview_purpose",
                "focus_topics",
                "exclude_topics",
                "interview_style",
                "changed_fields",
            ],
            "additionalProperties": False,
        },
    },
}


class StakeholderPlanService:

    def assist_slot_draft(
        self,
        project: Project,
        *,
        current_draft: Optional[Dict[str, Any]] = None,
        transcript: Optional[str] = None,
        existing_role_labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create or refine one stakeholder-role draft without saving it."""
        if not transcript and not current_draft:
            raise ValueError("transcript or current_draft is required")

        from app.core.config import settings
        from app.services.openai_service import openai_service

        project_context = {
            "title": to_traditional_zh(project.title),
            "description": to_traditional_zh(project.description or ""),
            "brd_scope": project.brd_scope or {},
        }
        existing_roles = [
            str(label).strip() for label in (existing_role_labels or []) if str(label).strip()
        ]
        mode_instruction = (
            "根據使用者的口說內容建立完整草稿；口說未明確提到的欄位，依專案背景合理補齊。"
            if transcript
            else (
                "補齊空白或資訊不足的文字欄位，並讓已有內容更具體、自然、可直接使用。"
                "角色類型、重要性、最低訪談場次與第一輪設定只是參考，系統會保留使用者原值。"
            )
        )
        user_payload = {
            "project": project_context,
            "existing_roles": existing_roles,
            "spoken_description": to_traditional_zh(transcript or ""),
            "current_draft": current_draft or {},
        }
        result = openai_service.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是資深需求訪談規劃顧問，負責協助使用者撰寫單一受訪角色草稿。\n"
                        f"{mode_instruction}\n"
                        "角色名稱要貼合專案語境，避免和既有角色重複。\n"
                        "訪談目的用「了解」「釐清」「確認」等中性動詞開頭，不要使用「只有他們能」、"
                        "「唯有此角色」等排他句型。\n"
                        "預期取得的資訊請提供 3-4 個精簡項目。\n"
                        "關鍵問題請提供 4-6 題；每題只問一件事，使用自然口語，並從具體經驗切入。\n"
                        "所有輸出文字必須使用台灣繁體中文，不可使用簡體中文。\n"
                        "只回傳符合指定 schema 的 JSON。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            model=settings.SEMANTIC_UNDERSTANDING_MODEL,
            temperature=0.2,
            max_tokens=1600,
            response_format=STAKEHOLDER_SLOT_DRAFT_RESPONSE_FORMAT,
            purpose=("stakeholder_slot_voice_parse" if transcript else "stakeholder_slot_refine"),
        )
        normalized = self._validate_slot_draft(result)

        # Refinement must not silently override explicit planning choices.
        if current_draft and not transcript:
            normalized["role_category"] = self._normalize_role_category(
                current_draft.get("role_category")
            )
            normalized["priority"] = self._normalize_priority(current_draft.get("priority"))
            normalized["min_interviews"] = self._normalize_min_interviews(
                current_draft.get("min_interviews")
            )
            normalized["first_wave"] = bool(current_draft.get("first_wave", False))

        return normalized

    def assist_profile_draft(
        self,
        project: Project,
        *,
        transcript: str,
        slot_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extract an unsaved stakeholder profile from a spoken description."""
        if not transcript.strip():
            raise ValueError("transcript is required")

        from app.core.config import settings
        from app.services.openai_service import openai_service

        user_payload = {
            "project": {
                "title": to_traditional_zh(project.title),
                "description": to_traditional_zh(project.description or ""),
                "brd_scope": project.brd_scope or {},
            },
            "slot": slot_context or {},
            "spoken_description": to_traditional_zh(transcript),
        }
        result = openai_service.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你負責把使用者口述的受訪者資料整理成表單草稿。\n"
                        "姓名、職稱、部門、專長與不熟悉領域只能擷取口述中明確提供的資訊，"
                        "未提及時請回傳空字串或空陣列，不可杜撰個人資料。\n"
                        "stakeholder_type 可依職稱、部門、專案與受訪角色脈絡分類。\n"
                        "專長與不熟悉領域各保留最多 5 個簡短、自然的繁體中文項目。\n"
                        "所有輸出文字必須使用台灣繁體中文，不可使用簡體中文。\n"
                        "只回傳符合指定 schema 的 JSON。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            model=settings.SEMANTIC_UNDERSTANDING_MODEL,
            temperature=0.1,
            max_tokens=700,
            response_format=STAKEHOLDER_PROFILE_DRAFT_RESPONSE_FORMAT,
            purpose="stakeholder_profile_voice_parse",
        )
        return self._validate_profile_draft(result)

    def _validate_profile_draft(self, result: Any) -> Dict[str, Any]:
        """Validate and normalize a generated stakeholder-profile draft."""
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict):
            raise TypeError(f"expected object, got {type(result).__name__}")

        return {
            "name": to_traditional_zh(str(result.get("name", ""))),
            "role_title": to_traditional_zh(str(result.get("role_title", ""))),
            "department": to_traditional_zh(str(result.get("department", ""))),
            "stakeholder_type": self._normalize_role_category(result.get("stakeholder_type")),
            "expertise_tags": self._normalize_string_list(result.get("expertise_tags"))[:5],
            "knowledge_boundaries": self._normalize_string_list(result.get("knowledge_boundaries"))[
                :5
            ],
        }

    def assist_interview_guide_draft(
        self,
        project: Project,
        *,
        transcript: str,
        profile_context: Dict[str, Any],
        current_draft: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply spoken guide preferences to an unsaved interview-guide draft."""
        if not transcript.strip():
            raise ValueError("transcript is required")

        from app.core.config import settings
        from app.services.openai_service import openai_service

        user_payload = {
            "project": {
                "title": to_traditional_zh(project.title),
                "description": to_traditional_zh(project.description or ""),
                "brd_scope": project.brd_scope or {},
            },
            "participant": profile_context,
            "current_draft": current_draft,
            "spoken_instruction": to_traditional_zh(transcript),
        }
        result = openai_service.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你負責把使用者口述的訪談大綱偏好套用到現有草稿。\n"
                        "可調整欄位只有：訪談時長、訪談目的、聚焦主題、排除主題、訪談風格。\n"
                        "changed_fields 只列出口述中有要求新增、修改或清除的欄位；"
                        "未提及的欄位必須保留 current_draft 原值。\n"
                        "時長限制 10 到 90 分鐘並取最接近的 5 分鐘。\n"
                        "訪談風格只能是 exploratory、structured、validation 或空字串。\n"
                        "文字使用自然、精簡的繁體中文；多個主題用頓號分隔。\n"
                        "所有輸出文字必須使用台灣繁體中文，不可使用簡體中文。\n"
                        "只回傳符合指定 schema 的 JSON。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            model=settings.SEMANTIC_UNDERSTANDING_MODEL,
            temperature=0.1,
            max_tokens=700,
            response_format=INTERVIEW_GUIDE_DRAFT_RESPONSE_FORMAT,
            purpose="interview_guide_voice_parse",
        )
        return self._merge_interview_guide_draft(current_draft, result)

    @staticmethod
    def _merge_interview_guide_draft(current_draft: Dict[str, Any], result: Any) -> Dict[str, Any]:
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict):
            raise TypeError(f"expected object, got {type(result).__name__}")

        allowed_fields = {
            "duration_minutes",
            "interview_purpose",
            "focus_topics",
            "exclude_topics",
            "interview_style",
        }
        changed_fields = {
            str(field) for field in result.get("changed_fields", []) if field in allowed_fields
        }
        merged = {
            "duration_minutes": current_draft.get("duration_minutes", 30),
            "interview_purpose": to_traditional_zh(
                str(current_draft.get("interview_purpose", "") or "")
            ),
            "focus_topics": to_traditional_zh(str(current_draft.get("focus_topics", "") or "")),
            "exclude_topics": to_traditional_zh(str(current_draft.get("exclude_topics", "") or "")),
            "interview_style": str(current_draft.get("interview_style", "") or "").strip(),
        }

        if "duration_minutes" in changed_fields:
            try:
                duration = int(result.get("duration_minutes", 30))
            except (TypeError, ValueError):
                duration = 30
            merged["duration_minutes"] = min(90, max(10, round(duration / 5) * 5))

        for field in ("interview_purpose", "focus_topics", "exclude_topics"):
            if field in changed_fields:
                merged[field] = to_traditional_zh(str(result.get(field, "") or ""))

        if "interview_style" in changed_fields:
            style = result.get("interview_style")
            merged["interview_style"] = (
                style if style in {"exploratory", "structured", "validation", ""} else ""
            )

        return merged

    def _validate_slot_draft(self, result: Any) -> Dict[str, Any]:
        """Validate and normalize a generated stakeholder-role draft."""
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict):
            raise TypeError(f"expected object, got {type(result).__name__}")

        role_label = to_traditional_zh(str(result.get("role_label", "")))
        if not role_label:
            raise ValueError("stakeholder slot draft has no role_label")

        return {
            "role_category": self._normalize_role_category(result.get("role_category")),
            "role_label": role_label,
            "rationale": self._neutralize_rationale(
                to_traditional_zh(str(result.get("rationale", "")))
            ),
            "expected_contributions": self._normalize_string_list(
                result.get("expected_contributions")
            ),
            "key_questions_to_cover": self._normalize_string_list(
                result.get("key_questions_to_cover")
            ),
            "priority": self._normalize_priority(result.get("priority")),
            "min_interviews": self._normalize_min_interviews(result.get("min_interviews")),
            "first_wave": bool(result.get("first_wave", False)),
        }

    @staticmethod
    def _normalize_string_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [to_traditional_zh(str(item)) for item in value if str(item).strip()]

    @staticmethod
    def _normalize_role_category(value: Any) -> str:
        return value if value in ROLE_CATEGORIES else "other"

    @staticmethod
    def _normalize_priority(value: Any) -> str:
        return value if value in ("required", "recommended", "optional") else "required"

    @staticmethod
    def _normalize_min_interviews(value: Any) -> int:
        try:
            return min(20, max(1, int(value)))
        except (TypeError, ValueError):
            return 1

    def generate_initial_plan(self, db: Session, project_id: str) -> List[StakeholderSlot]:
        """Generate initial stakeholder slots from project brd_scope using AI."""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return []

        # Use AI to analyze brd_scope and recommend roles
        slots = self._ai_suggest_slots(project)

        for i, slot_data in enumerate(slots):
            rationale = slot_data.get("rationale", "")
            conditions = slot_data.get("conditions", "")
            if conditions:
                rationale = f"{rationale}（條件：{conditions}）"

            slot = StakeholderSlot(
                id=f"slot_{uuid.uuid4().hex[:12]}",
                project_id=project_id,
                role_category=slot_data.get("role_category", "business"),
                role_label=slot_data.get("role_label", "未命名角色"),
                rationale=rationale,
                expected_contributions=slot_data.get("expected_contributions", []),
                key_questions_to_cover=slot_data.get("key_questions_to_cover", []),
                priority=slot_data.get("priority", "required"),
                min_interviews=slot_data.get("min_interviews", 1),
                first_wave=slot_data.get("first_wave", i < 2),
                order_index=i,
                source=slot_data.get("source", "ai_suggested"),
            )
            db.add(slot)

        db.commit()
        return (
            db.query(StakeholderSlot)
            .filter(StakeholderSlot.project_id == project_id)
            .order_by(StakeholderSlot.order_index)
            .all()
        )

    def _ai_suggest_slots(self, project: Project) -> List[Dict[str, Any]]:
        """Use AI to suggest stakeholder slots based on project title and description."""
        try:
            from app.services.openai_service import openai_service

            system_prompt = (
                "你是資深的需求分析顧問。你的任務是根據專案描述，建立能完整覆蓋需求的利害關係人訪談計劃。\n\n"
                "嚴格規則：\n"
                "1. 不要為了符合固定數量而省略重要角色。簡單專案可以只有 2 個；一般專案通常 3-5 個；跨部門、整合型、受監管或高風險專案可以更多。\n"
                "2. 每個角色必須有明確不同的「知識領域」。如果兩個角色可能是同一個人，就合併。\n"
                "3. 角色名稱要用這個專案的語言，不要用通用職稱。例如：\n"
                "   - 「簡報助手」專案 → 用「實際簡報者」而非「最終使用者」\n"
                "   - 「餐廳 POS」專案 → 用「外場服務人員」而非「一線操作者」\n"
                "4. 問題必須是一句可以直接開口問的話，像在對話中自然提出。\n"
                "   - 好：「上次你準備簡報的時候，花最多時間的是哪一步？」\n"
                "   - 壞：「請描述你的簡報準備流程與痛點。」\n"
                "5. 每個問題只問一件事。不要用「以及」「和」連接兩個問題。\n"
                "6. 問題要從具體經驗出發，不要問抽象定義。先問「上次發生什麼」，再問「通常怎麼處理」。\n"
                "7. 完整計劃至少要評估實際使用者、流程負責人、決策或驗收人員。涉及既有系統時評估技術整合角色。\n"
                "8. 醫療、金融、兒少、身份資料等領域即使描述未明說，也要評估隱私、法規、安全或高風險作業角色。\n"
                "9. 用 first_wave 標示第一輪最優先訪談的 2-3 個角色；完整角色清單不受第一輪數量限制。\n\n"
                '只回傳符合指定 schema 的 JSON 物件，頂層格式為 {"slots": [...]}。'
            )

            user_prompt = (
                f"專案名稱：{project.title}\n"
                f"專案描述：{project.description or '無'}\n\n"
                '請產出最少但足以完整覆蓋需求的訪談角色。回傳 JSON 物件 {"slots": [...]}，每個角色包含：\n'
                "- role_category: 角色類別 (business/product/engineering/management/operations/customer_support/legal/finance/design/qa/user)\n"
                "- role_label: 角色名稱（中文，用這個專案的語言命名）\n"
                "- rationale: 一句話說明為什麼要訪談此角色，以及預期補足哪些資訊缺口。"
                "用「了解」「釐清」「確認」等中性動詞開頭；不要使用「只有他／他們能」、"
                "「唯有此角色」或其他排他、誇大的句型\n"
                "- expected_contributions: 這個角色獨有的資訊（字串陣列，3-4 項，每項一個短句）\n"
                "- key_questions_to_cover: 具體訪談問題（字串陣列，4-6 個）\n"
                "  每個問題的要求：\n"
                "  - 一句話，可以直接開口問\n"
                "  - 只問一件事\n"
                "  - 從具體經驗切入（「上次...」「最近一次...」「能不能舉個例子...」）\n"
                "  - 對準這個角色的第一手經驗、職責或決策權限，避免任何人都能回答的通用問題\n"
                "- priority: required / recommended\n"
                "- min_interviews: 人數（提供第一手使用經驗的角色填 2-3，決策者填 1）\n"
                "- conditions: recommended 角色填寫觸發條件，required 留空字串\n\n"
                "- first_wave: 是否屬於第一輪最優先訪談角色（布林值；整份計劃選 2-3 個）\n\n"
                "角色順序 = 建議訪談順序，first_wave 角色排在前面。第一輪需兼顧流程全貌與第一手使用經驗，技術或風險若是主要阻礙也可列入。\n\n"
                "不要加入的角色：\n"
                "- 產品還在概念階段 → 不加客服\n"
                "- 發起人就是產品決策者 → 不另外加產品經理\n"
                "- 兩個角色的知識領域重疊超過 50% → 合併成一個\n"
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            last_error: Optional[Exception] = None
            for attempt in range(2):
                result = openai_service.chat_completion(
                    messages=messages,
                    model="gpt-5.4-mini",
                    temperature=0.4,
                    max_tokens=4000,
                    response_format=STAKEHOLDER_PLAN_RESPONSE_FORMAT,
                    purpose="stakeholder_plan_generation",
                )
                try:
                    return self._validate_ai_slots(result)
                except (TypeError, ValueError, json.JSONDecodeError) as e:
                    last_error = e
                    logger.warning(
                        "Invalid stakeholder plan shape on attempt %s: %s",
                        attempt + 1,
                        e,
                    )
                    messages = messages + [
                        {
                            "role": "user",
                            "content": (
                                "上一次輸出未通過格式驗證。請重新輸出完整 JSON 物件 "
                                '{"slots": [...]}，至少 2 個角色，並標示 2-3 個 first_wave。'
                            ),
                        }
                    ]

            if last_error:
                raise last_error

        except Exception as e:
            logger.warning(f"AI slot generation failed, using defaults: {e}")

        return self._default_slots(project)

    def _validate_ai_slots(self, result: Any) -> List[Dict[str, Any]]:
        """Validate and normalize the structured stakeholder plan response."""
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict):
            raise TypeError(f"expected object, got {type(result).__name__}")

        slots = result.get("slots")
        if not isinstance(slots, list):
            raise TypeError("missing slots array")
        if len(slots) < 2:
            raise ValueError("stakeholder plan must contain at least 2 roles")

        normalized: List[Dict[str, Any]] = []
        labels = set()
        for index, slot in enumerate(slots):
            if not isinstance(slot, dict):
                raise TypeError(f"slot {index} is not an object")
            label = str(slot.get("role_label", "")).strip()
            if not label:
                raise ValueError(f"slot {index} has no role_label")
            label_key = label.casefold()
            if label_key in labels:
                logger.warning("Dropping duplicated stakeholder role: %s", label)
                continue
            labels.add(label_key)

            role_category = slot.get("role_category", "other")
            if role_category not in ROLE_CATEGORIES:
                role_category = "other"

            normalized.append(
                {
                    "role_category": role_category,
                    "role_label": label,
                    "rationale": self._neutralize_rationale(slot.get("rationale", "")),
                    "expected_contributions": [
                        str(item).strip()
                        for item in slot.get("expected_contributions", [])
                        if str(item).strip()
                    ],
                    "key_questions_to_cover": [
                        str(item).strip()
                        for item in slot.get("key_questions_to_cover", [])
                        if str(item).strip()
                    ],
                    "priority": (
                        slot.get("priority")
                        if slot.get("priority") in ("required", "recommended", "optional")
                        else "required"
                    ),
                    "min_interviews": max(1, int(slot.get("min_interviews", 1))),
                    "conditions": str(slot.get("conditions", "")).strip(),
                    "first_wave": bool(slot.get("first_wave", False)),
                    "source": "ai_suggested",
                }
            )

        if len(normalized) < 2:
            raise ValueError("stakeholder plan has fewer than 2 unique roles")

        first_wave_count = sum(1 for slot in normalized if slot["first_wave"])
        if first_wave_count < 2:
            for slot in normalized[: min(3, len(normalized))]:
                slot["first_wave"] = True
        elif first_wave_count > 3:
            seen = 0
            for slot in normalized:
                if slot["first_wave"]:
                    seen += 1
                    if seen > 3:
                        slot["first_wave"] = False

        normalized.sort(key=lambda slot: not slot["first_wave"])
        return normalized

    @staticmethod
    def _neutralize_rationale(value: Any) -> str:
        """Remove model-generated exclusivity claims from user-facing rationale text."""
        rationale = str(value or "").strip()
        return EXCLUSIVE_RATIONALE_PREFIX.sub("了解", rationale, count=1)

    def _default_slots(self, project: Project) -> List[Dict[str, Any]]:
        """Transparent generic fallback used only when structured generation fails."""
        return [
            {
                "role_category": "user",
                "role_label": "實際使用者",
                "rationale": f"了解實際使用「{project.title}」時的流程、情境與障礙",
                "expected_contributions": ["實際流程", "常見情境", "操作痛點", "例外狀況"],
                "key_questions_to_cover": [
                    "最近一次處理這項工作時，完整流程是什麼？",
                    "上次遇到例外狀況時，你是怎麼處理的？",
                    "哪一個步驟最容易花費額外時間？",
                ],
                "priority": "required",
                "min_interviews": 2,
                "conditions": "",
                "first_wave": True,
                "source": "fallback",
            },
            {
                "role_category": "management",
                "role_label": "流程負責人 / 決策者",
                "rationale": "確認流程規則、優先順序、例外處理與驗收標準",
                "expected_contributions": ["流程規則", "決策原則", "驗收標準", "成功指標"],
                "key_questions_to_cover": [
                    "最近一次調整流程規則時，原因是什麼？",
                    "遇到資源衝突時，你通常如何決定優先順序？",
                    "你會用什麼結果判斷系統已經成功？",
                ],
                "priority": "required",
                "min_interviews": 1,
                "conditions": "",
                "first_wave": True,
                "source": "fallback",
            },
            {
                "role_category": "engineering",
                "role_label": "技術 / 系統整合負責人",
                "rationale": "確認既有系統、資料、安全與整合限制",
                "expected_contributions": ["既有系統", "資料流", "整合限制", "安全需求"],
                "key_questions_to_cover": [
                    "最近一次整合類似系統時，最大的限制是什麼？",
                    "哪些既有資料或系統一定要沿用？",
                    "發生服務中斷時，目前怎麼恢復？",
                ],
                "priority": "recommended",
                "min_interviews": 1,
                "conditions": "專案涉及既有系統、資料交換或正式上線時需要",
                "first_wave": False,
                "source": "fallback",
            },
        ]

    def create_slot(self, db: Session, project_id: str, data: Dict[str, Any]) -> StakeholderSlot:
        """Manually create a stakeholder slot."""
        max_order = (
            db.query(StakeholderSlot).filter(StakeholderSlot.project_id == project_id).count()
        )

        slot = StakeholderSlot(
            id=f"slot_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            role_category=data["role_category"],
            role_label=data["role_label"],
            rationale=data.get("rationale"),
            expected_contributions=data.get("expected_contributions", []),
            key_questions_to_cover=data.get("key_questions_to_cover", []),
            priority=data.get("priority", "required"),
            min_interviews=data.get("min_interviews", 1),
            first_wave=data.get("first_wave", False),
            order_index=max_order,
            source="user_created",
        )
        db.add(slot)
        db.commit()
        db.refresh(slot)
        return slot

    def update_slot(
        self, db: Session, slot_id: str, data: Dict[str, Any]
    ) -> Optional[StakeholderSlot]:
        slot = db.query(StakeholderSlot).filter(StakeholderSlot.id == slot_id).first()
        if not slot:
            return None
        for key, value in data.items():
            if value is not None and hasattr(slot, key):
                setattr(slot, key, value)
        slot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(slot)
        return slot

    def delete_slot(self, db: Session, slot_id: str) -> bool:
        slot = db.query(StakeholderSlot).filter(StakeholderSlot.id == slot_id).first()
        if not slot:
            return False
        project_id = slot.project_id
        deleted_order = slot.order_index

        assigned_profiles = (
            db.query(StakeholderProfileSlot.id)
            .filter(StakeholderProfileSlot.slot_id == slot_id)
            .count()
        )
        if assigned_profiles > 0:
            raise StakeholderSlotHasProfilesError(
                "此角色底下仍有已指派受訪者，請先移除受訪者後再刪除角色。"
            )

        db.delete(slot)
        db.query(StakeholderSlot).filter(
            StakeholderSlot.project_id == project_id,
            StakeholderSlot.order_index > deleted_order,
        ).update(
            {StakeholderSlot.order_index: StakeholderSlot.order_index - 1},
            synchronize_session=False,
        )
        db.commit()
        return True

    def skip_slot(self, db: Session, slot_id: str) -> Optional[StakeholderSlot]:
        return self.update_slot(db, slot_id, {"status": "skipped"})

    def unskip_slot(self, db: Session, slot_id: str) -> Optional[StakeholderSlot]:
        return self.update_slot(db, slot_id, {"status": "unassigned"})

    def reorder_slots(self, db: Session, slot_ids: List[str]) -> None:
        """Update order_index for slots based on the given ID order."""
        for i, slot_id in enumerate(slot_ids):
            slot = db.query(StakeholderSlot).filter(StakeholderSlot.id == slot_id).first()
            if slot:
                slot.order_index = i
        db.commit()

    def create_profile(
        self, db: Session, project_id: str, data: Dict[str, Any]
    ) -> StakeholderProfile:
        """Create a stakeholder profile."""
        profile = StakeholderProfile(
            id=f"stkh_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            name=data["name"],
            role_title=data.get("role_title"),
            department=data.get("department"),
            stakeholder_type=data["stakeholder_type"],
            expertise_tags=data.get("expertise_tags", []),
            knowledge_boundaries=data.get("knowledge_boundaries", []),
            decision_power=data.get("decision_power"),
            notes=data.get("notes"),
        )
        db.add(profile)
        db.flush()

        self._replace_profile_slots(
            db,
            profile,
            data.get("slot_ids", []),
            data.get("primary_slot_id"),
        )

        db.commit()
        db.refresh(profile)
        self._update_slot_statuses(db, project_id)
        return profile

    def update_profile(
        self, db: Session, profile_id: str, data: Dict[str, Any]
    ) -> Optional[StakeholderProfile]:
        profile = db.query(StakeholderProfile).filter(StakeholderProfile.id == profile_id).first()
        if not profile:
            return None

        for key, value in data.items():
            if value is not None and hasattr(profile, key):
                setattr(profile, key, value)
        profile.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(profile)

        self._update_slot_statuses(db, profile.project_id)
        return profile

    def delete_profile(self, db: Session, profile_id: str) -> bool:
        profile = db.query(StakeholderProfile).filter(StakeholderProfile.id == profile_id).first()
        if not profile:
            return False
        project_id = profile.project_id

        self._delete_profile_guide(db, profile)

        db.delete(profile)
        db.commit()
        self._update_slot_statuses(db, project_id)
        return True

    def _delete_profile_guide(self, db: Session, profile: StakeholderProfile) -> None:
        """Delete the interview guide document associated with this profile."""
        from app.models.document import Document
        from app.services.document_service import DocumentService

        document = (
            db.query(Document)
            .filter(
                Document.stakeholder_profile_id == profile.id,
                Document.source_file_url == "generated",
            )
            .first()
        )
        if document:
            DocumentService.delete_document(db, document.id, commit=True)

    def cancel_profile(self, db: Session, profile_id: str) -> Optional[StakeholderProfile]:
        return self.update_profile(db, profile_id, {"status": "unavailable"})

    def set_profile_slots(
        self,
        db: Session,
        profile_id: str,
        slot_ids: List[str],
        primary_slot_id: Optional[str] = None,
    ) -> Optional[StakeholderProfile]:
        """Replace a profile's many-to-many role assignments."""
        profile = db.query(StakeholderProfile).filter(StakeholderProfile.id == profile_id).first()
        if not profile:
            return None

        self._replace_profile_slots(db, profile, slot_ids, primary_slot_id)
        profile.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(profile)
        self._update_slot_statuses(db, profile.project_id)
        return profile

    def _replace_profile_slots(
        self,
        db: Session,
        profile: StakeholderProfile,
        slot_ids: Optional[List[str]],
        primary_slot_id: Optional[str] = None,
    ) -> None:
        normalized_slot_ids = list(dict.fromkeys(slot_ids or []))
        if primary_slot_id and primary_slot_id not in normalized_slot_ids:
            normalized_slot_ids.insert(0, primary_slot_id)
        if normalized_slot_ids:
            slots_found = (
                db.query(StakeholderSlot.id)
                .filter(
                    StakeholderSlot.project_id == profile.project_id,
                    StakeholderSlot.id.in_(normalized_slot_ids),
                )
                .all()
            )
            existing = {row[0] for row in slots_found}
            missing = [slot_id for slot_id in normalized_slot_ids if slot_id not in existing]
            if missing:
                raise StakeholderProfileSlotNotFoundError("找不到要指派的角色。")

        primary = primary_slot_id or (normalized_slot_ids[0] if normalized_slot_ids else None)

        db.query(StakeholderProfileSlot).filter(
            StakeholderProfileSlot.profile_id == profile.id
        ).delete(synchronize_session=False)
        for slot_id in normalized_slot_ids:
            db.add(
                StakeholderProfileSlot(
                    id=f"stps_{uuid.uuid4().hex[:12]}",
                    project_id=profile.project_id,
                    profile_id=profile.id,
                    slot_id=slot_id,
                    is_primary=(slot_id == primary),
                )
            )

    def get_plan_status(self, db: Session, project_id: str) -> Dict[str, Any]:
        """Get current stakeholder plan status overview."""
        slots = (
            db.query(StakeholderSlot)
            .filter(StakeholderSlot.project_id == project_id)
            .order_by(StakeholderSlot.order_index)
            .all()
        )

        profiles = (
            db.query(StakeholderProfile).filter(StakeholderProfile.project_id == project_id).all()
        )
        assignments = (
            db.query(StakeholderProfileSlot)
            .filter(StakeholderProfileSlot.project_id == project_id)
            .all()
        )
        profiles_by_id = {p.id: p for p in profiles}
        profiles_by_slot: Dict[str, List[StakeholderProfile]] = {}
        for assignment in assignments:
            profile = profiles_by_id.get(assignment.profile_id)
            if profile:
                profiles_by_slot.setdefault(assignment.slot_id, []).append(profile)

        slot_details = []
        total_required = 0
        completed_required = 0

        for slot in slots:
            slot_profiles = profiles_by_slot.get(slot.id, [])
            interviews_done = sum(p.interview_count for p in slot_profiles)

            detail = {
                "id": slot.id,
                "role_label": slot.role_label,
                "role_category": slot.role_category,
                "priority": slot.priority,
                "status": slot.status,
                "profiles_count": len(slot_profiles),
                "min_interviews": slot.min_interviews,
                "first_wave": slot.first_wave,
                "interviews_done": interviews_done,
            }
            slot_details.append(detail)

            if slot.priority == "required":
                total_required += 1
                if slot.status == "completed":
                    completed_required += 1

        progress = (completed_required / total_required * 100) if total_required > 0 else 0

        # Determine next recommended action
        next_action = None
        prioritized_slots = sorted(slots, key=lambda slot: (not slot.first_wave, slot.order_index))
        for slot in prioritized_slots:
            if slot.status in ("unassigned", "partially_assigned") and slot.priority == "required":
                next_action = {
                    "action": "arrange_interview",
                    "target_role": slot.role_label,
                    "role_category": slot.role_category,
                    "reason": f"角色「{slot.role_label}」尚未安排訪談",
                }
                break

        return {
            "total_slots": len(slots),
            "completed_slots": len([s for s in slots if s.status == "completed"]),
            "progress_percentage": round(progress, 1),
            "first_wave_total": len([s for s in slots if s.first_wave]),
            "first_wave_completed": len(
                [s for s in slots if s.first_wave and s.status == "completed"]
            ),
            "generation_source": (
                "fallback"
                if any(s.source == "fallback" for s in slots)
                else (
                    "ai_suggested"
                    if any(s.source == "ai_suggested" for s in slots)
                    else "user_created"
                )
            ),
            "slots": slot_details,
            "next_recommended_action": next_action,
        }

    def _update_slot_statuses(self, db: Session, project_id: str):
        """Recalculate all slot statuses based on their profiles and sessions."""
        slots = db.query(StakeholderSlot).filter(StakeholderSlot.project_id == project_id).all()

        for slot in slots:
            if slot.status == "skipped":
                continue

            profiles = (
                db.query(StakeholderProfile)
                .join(
                    StakeholderProfileSlot,
                    StakeholderProfileSlot.profile_id == StakeholderProfile.id,
                )
                .filter(
                    StakeholderProfileSlot.slot_id == slot.id,
                    StakeholderProfile.status != "unavailable",
                )
                .all()
            )

            if not profiles:
                slot.status = "unassigned"
            else:
                interviewed = [p for p in profiles if p.status == "interviewed"]
                total_interviews = sum(p.interview_count for p in profiles)

                if total_interviews >= slot.min_interviews:
                    slot.status = "completed"
                elif interviewed:
                    slot.status = "interviewing"
                elif len(profiles) < slot.min_interviews:
                    slot.status = "partially_assigned"
                else:
                    slot.status = "assigned"

        db.commit()

    def update_plan_after_interview(
        self, db: Session, project_id: str, _memo_id: str
    ) -> Dict[str, Any]:
        """Update plan after an interview completes (called after Insight Memo generation).

        For now, just recalculate slot statuses. In Phase 3+, this will also
        analyze memo.unresolved_questions to suggest new slots/profiles.
        """
        self._update_slot_statuses(db, project_id)
        return {"slots_updated": True}


stakeholder_plan_service = StakeholderPlanService()
