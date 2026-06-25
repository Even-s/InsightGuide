"""Stakeholder Plan service — dynamic interview planning engine."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.interview_session import InterviewSession
from app.models.project import Project
from app.models.stakeholder_profile import StakeholderProfile
from app.models.stakeholder_slot import StakeholderSlot

logger = logging.getLogger(__name__)


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
]


class StakeholderPlanService:

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
                order_index=i,
                source="ai_suggested",
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
            import json

            from app.services.openai_service import openai_service

            system_prompt = (
                "你是資深的需求分析顧問。你的任務是根據專案描述，判斷「初始階段最少需要找哪幾種人聊」。\n\n"
                "嚴格規則：\n"
                "1. 初始只產出 2-3 個角色。不要超過 3 個。其他角色會在訪談過程中根據發現動態加入。\n"
                "2. 每個角色必須有明確不同的「知識領域」。如果兩個角色可能是同一個人，就合併。\n"
                "3. 角色名稱要用這個專案的語言，不要用通用職稱。例如：\n"
                "   - 「簡報助手」專案 → 用「實際簡報者」而非「最終使用者」\n"
                "   - 「餐廳 POS」專案 → 用「外場服務人員」而非「一線操作者」\n"
                "4. 問題必須是一句可以直接開口問的話，像在對話中自然提出。\n"
                "   - 好：「上次你準備簡報的時候，花最多時間的是哪一步？」\n"
                "   - 壞：「請描述你的簡報準備流程與痛點。」\n"
                "5. 每個問題只問一件事。不要用「以及」「和」連接兩個問題。\n"
                "6. 問題要從具體經驗出發，不要問抽象定義。先問「上次發生什麼」，再問「通常怎麼處理」。\n\n"
                "只回傳 JSON 陣列。"
            )

            user_prompt = (
                f"專案名稱：{project.title}\n"
                f"專案描述：{project.description or '無'}\n\n"
                "請產出 2-3 個初始訪談角色。回傳 JSON 陣列，每個元素：\n"
                "- role_category: 角色類別 (business/product/engineering/management/operations/customer_support/legal/finance/design/qa/user)\n"
                "- role_label: 角色名稱（中文，用這個專案的語言命名）\n"
                "- rationale: 一句話說明「只有這個人能告訴我什麼」\n"
                "- expected_contributions: 這個角色獨有的資訊（字串陣列，3-4 項，每項一個短句）\n"
                "- key_questions_to_cover: 具體訪談問題（字串陣列，4-6 個）\n"
                "  每個問題的要求：\n"
                "  - 一句話，可以直接開口問\n"
                "  - 只問一件事\n"
                "  - 從具體經驗切入（「上次...」「最近一次...」「能不能舉個例子...」）\n"
                "  - 只有這個角色能回答（如果別的角色也能答，就不該問這題）\n"
                "- priority: required / recommended\n"
                "- min_interviews: 人數（提供第一手使用經驗的角色填 2-3，決策者填 1）\n"
                "- conditions: recommended 角色填寫觸發條件，required 留空字串\n\n"
                "角色順序 = 訪談順序：\n"
                "第 1 位：能給你全局背景和決策權的人（通常 1 位）\n"
                "第 2 位：實際會使用這個產品的人（通常 2-3 位，涵蓋不同情境）\n"
                "第 3 位（如果需要）：能回答技術可行性或特殊限制的人\n\n"
                "不要加入的角色：\n"
                "- 專案描述沒提到個資/錄音/法規 → 不加法務\n"
                "- 產品還在概念階段 → 不加客服\n"
                "- 發起人就是產品決策者 → 不另外加產品經理\n"
                "- 兩個角色的知識領域重疊超過 50% → 合併成一個\n"
            )

            result = openai_service.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="gpt-5.4-mini",
                temperature=0.4,
                max_tokens=2500,
                response_format={"type": "json_object"},
                db=db,
                purpose="stakeholder_plan_generation",
            )

            # The wrapper already parses JSON, but handle markdown code blocks if present
            if isinstance(result, str):
                content = result.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                slots = json.loads(content)
            else:
                slots = result
            if isinstance(slots, list) and len(slots) > 0:
                return slots

        except Exception as e:
            logger.warning(f"AI slot generation failed, using defaults: {e}")

        return self._default_slots(project)

    def _default_slots(self, project: Project) -> List[Dict[str, Any]]:
        """Fallback: return sensible default slots."""
        return [
            {
                "role_category": "business",
                "role_label": "業務 / 銷售",
                "rationale": "了解客戶需求來源與現有流程痛點",
                "expected_contributions": ["客戶流程", "痛點", "需求來源", "使用情境"],
                "key_questions_to_cover": [
                    "目前怎麼管理需求？",
                    "最常見的客戶問題？",
                    "流程中最大的障礙？",
                ],
                "priority": "required",
                "min_interviews": 1,
            },
            {
                "role_category": "product",
                "role_label": "產品經理 (PM)",
                "rationale": "確認需求優先級、產品流程與驗收標準",
                "expected_contributions": ["需求排序", "產品路線圖", "驗收標準", "使用者故事"],
                "key_questions_to_cover": [
                    "需求如何被決定優先級？",
                    "什麼是成功的標準？",
                    "目前的產品流程？",
                ],
                "priority": "required",
                "min_interviews": 1,
            },
            {
                "role_category": "engineering",
                "role_label": "工程 / IT",
                "rationale": "確認技術可行性、系統限制與整合方式",
                "expected_contributions": ["技術限制", "系統整合", "API", "效能需求", "資料流"],
                "key_questions_to_cover": [
                    "現有系統的技術限制？",
                    "哪些整合是必須的？",
                    "效能需求？",
                ],
                "priority": "required",
                "min_interviews": 1,
            },
            {
                "role_category": "management",
                "role_label": "管理者 / 決策者",
                "rationale": "確認預算、KPI、時程與決策標準",
                "expected_contributions": ["預算", "KPI", "上線時程", "決策流程"],
                "key_questions_to_cover": ["預算範圍？", "成功的 KPI？", "上線時程期望？"],
                "priority": "recommended",
                "min_interviews": 1,
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
        db.delete(slot)
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
            slot_id=data.get("slot_id"),
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
        db.delete(profile)
        db.commit()
        self._update_slot_statuses(db, project_id)
        return True

    def cancel_profile(self, db: Session, profile_id: str) -> Optional[StakeholderProfile]:
        return self.update_profile(db, profile_id, {"status": "unavailable"})

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

        slot_details = []
        total_required = 0
        completed_required = 0

        for slot in slots:
            slot_profiles = [p for p in profiles if p.slot_id == slot.id]
            interviewed = [p for p in slot_profiles if p.status == "interviewed"]
            interviews_done = sum(p.interview_count for p in slot_profiles)

            detail = {
                "id": slot.id,
                "role_label": slot.role_label,
                "role_category": slot.role_category,
                "priority": slot.priority,
                "status": slot.status,
                "profiles_count": len(slot_profiles),
                "min_interviews": slot.min_interviews,
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
        for slot in slots:
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
                .filter(
                    StakeholderProfile.slot_id == slot.id,
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
        self, db: Session, project_id: str, memo_id: str
    ) -> Dict[str, Any]:
        """Update plan after an interview completes (called after Insight Memo generation).

        For now, just recalculate slot statuses. In Phase 3+, this will also
        analyze memo.unresolved_questions to suggest new slots/profiles.
        """
        self._update_slot_statuses(db, project_id)
        return {"slots_updated": True}


stakeholder_plan_service = StakeholderPlanService()
