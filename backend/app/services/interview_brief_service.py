"""Interview Brief Service - generates role-based interview plans."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.interview_brief import InterviewBrief
from app.models.interview_session import InterviewSession
from app.models.project import Project
from app.models.question_card import QuestionCard
from app.models.stakeholder_profile import StakeholderProfile

logger = logging.getLogger(__name__)


class InterviewBriefService:

    def generate_brief(self, db: Session, session_id: str) -> InterviewBrief:
        """Generate a role-based interview brief for a session.

        Requires the session to have project_id and stakeholder_profile_id set.
        """
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found")
        if not session.project_id or not session.stakeholder_profile_id:
            raise ValueError("Session must have project_id and stakeholder_profile_id")

        # Check for existing brief
        existing = db.query(InterviewBrief).filter(InterviewBrief.session_id == session_id).first()
        if existing:
            db.delete(existing)
            db.flush()

        stakeholder = (
            db.query(StakeholderProfile)
            .filter(StakeholderProfile.id == session.stakeholder_profile_id)
            .first()
        )
        project = db.query(Project).filter(Project.id == session.project_id).first()

        if not stakeholder or not project:
            raise ValueError("Stakeholder or project not found")

        # Filter cards by role
        from app.services.role_filter_service import role_filter_service

        cards = db.query(QuestionCard).filter(QuestionCard.document_id == session.document_id).all()
        categorized = role_filter_service.filter_cards_for_stakeholder(cards, stakeholder)

        applicable_cards = categorized["applicable"] + categorized["uncertain"]
        not_applicable_cards = categorized["not_applicable"]

        # Gather prior unresolved questions (from Phase 3 Insight Memos — stubbed for now)
        follow_ups = self._gather_prior_follow_ups(db, project.id, stakeholder)

        # Generate brief content using AI
        brief_content = self._ai_generate_brief(
            project=project,
            stakeholder=stakeholder,
            applicable_cards=applicable_cards,
            not_applicable_cards=not_applicable_cards,
            follow_ups=follow_ups,
        )

        brief = InterviewBrief(
            id=f"brief_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            stakeholder_profile_id=stakeholder.id,
            project_id=project.id,
            interview_objective=brief_content["interview_objective"],
            recommended_topics=brief_content["recommended_topics"],
            excluded_topics=brief_content["excluded_topics"],
            suggested_questions=brief_content["suggested_questions"],
            follow_up_from_prior_interviews=follow_ups,
            applicable_card_ids=[c.id for c in applicable_cards],
            not_applicable_cards=[
                {"card_id": c.id, "question": c.question_text, "target_roles": c.target_roles or []}
                for c in not_applicable_cards[:10]
            ],
            time_estimate_minutes=brief_content.get("time_estimate_minutes"),
            generated_at=datetime.utcnow(),
        )

        db.add(brief)
        db.commit()
        db.refresh(brief)
        return brief

    def get_brief(self, db: Session, session_id: str) -> Optional[InterviewBrief]:
        return db.query(InterviewBrief).filter(InterviewBrief.session_id == session_id).first()

    def _gather_prior_follow_ups(
        self, db: Session, project_id: str, stakeholder: StakeholderProfile
    ) -> List[Dict[str, Any]]:
        """Gather unresolved questions from prior Insight Memos that target this role.

        Stubbed for now — will be fully implemented in Phase 3 when
        InterviewInsightMemo exists.
        """
        # Phase 3 will query:
        # SELECT unresolved_questions FROM interview_insight_memos
        # WHERE project_id = ? AND suggested_stakeholder_type matches stakeholder
        return []

    def _ai_generate_brief(
        self,
        project: Project,
        stakeholder: StakeholderProfile,
        applicable_cards: List[QuestionCard],
        not_applicable_cards: List[QuestionCard],
        follow_ups: List[Dict],
    ) -> Dict[str, Any]:
        """Use AI to generate the interview brief content."""
        try:
            from app.services.openai_service import openai_service

            brd_scope = project.brd_scope or {}
            card_summaries = [
                f"- {c.question_text} ({c.question_type}, {c.importance})"
                for c in applicable_cards[:15]
            ]

            prompt = (
                "你是專業的訪談規劃師。根據以下資訊，產生一份訪談前計劃。\n\n"
                f"## 專案\n"
                f"名稱：{project.title}\n"
                f"目標：{', '.join(brd_scope.get('key_objectives', []))}\n"
                f"領域：{brd_scope.get('business_domain', '未指定')}\n\n"
                f"## 受訪者\n"
                f"姓名：{stakeholder.name}\n"
                f"角色：{stakeholder.role_title or stakeholder.stakeholder_type}\n"
                f"部門：{stakeholder.department or '未指定'}\n"
                f"專長：{', '.join(stakeholder.expertise_tags or [])}\n"
                f"不熟悉：{', '.join(stakeholder.knowledge_boundaries or [])}\n\n"
                f"## 適合此角色的問題 ({len(applicable_cards)} 題)\n"
                + "\n".join(card_summaries[:15])
                + "\n\n"
                f"## 不適合此角色的問題 ({len(not_applicable_cards)} 題，將被跳過)\n\n"
                "請產生 JSON 格式的訪談計劃：\n"
                "{\n"
                '  "interview_objective": "一句話描述本次訪談目標",\n'
                '  "recommended_topics": [\n'
                '    {"topic": "主題", "reason": "為什麼要問", "priority": "high|medium|low"}\n'
                "  ],\n"
                '  "excluded_topics": [\n'
                '    {"topic": "主題", "reason": "為什麼不該問這位受訪者"}\n'
                "  ],\n"
                '  "suggested_questions": [\n'
                '    {"question": "建議的開場問題", "intent": "目的", "expected_insight": "預期得到什麼"}\n'
                "  ],\n"
                '  "time_estimate_minutes": 45\n'
                "}\n\n"
                "規則：\n"
                "- recommended_topics 3-5 個，按 priority 排序\n"
                "- excluded_topics 列出受訪者不熟悉的領域\n"
                "- suggested_questions 3-5 個，用受訪者容易理解的語言\n"
                "- 只回傳 JSON，不要其他文字"
            )

            ai_result = openai_service.chat_completion(
                messages=[
                    {"role": "system", "content": "你是專業的訪談規劃師。只回傳 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                model="gpt-5.4-mini",
                temperature=0.3,
                max_tokens=1200,
                response_format={"type": "json_object"},
                purpose="interview_brief_generation",
            )

            # The wrapper already parses JSON, but handle markdown code blocks if present
            if isinstance(ai_result, str):
                content = ai_result.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                result = json.loads(content)
            else:
                result = ai_result
            return {
                "interview_objective": result.get(
                    "interview_objective",
                    f"訪問 {stakeholder.name} 了解 {stakeholder.stakeholder_type} 視角",
                ),
                "recommended_topics": result.get("recommended_topics", []),
                "excluded_topics": result.get("excluded_topics", []),
                "suggested_questions": result.get("suggested_questions", []),
                "time_estimate_minutes": result.get("time_estimate_minutes", 45),
            }

        except Exception as e:
            logger.warning(f"AI brief generation failed, using defaults: {e}")
            return self._fallback_brief(project, stakeholder, applicable_cards)

    def _fallback_brief(
        self, project: Project, stakeholder: StakeholderProfile, cards: List[QuestionCard]
    ) -> Dict[str, Any]:
        """Fallback brief when AI is unavailable."""
        return {
            "interview_objective": f"了解 {stakeholder.name}（{stakeholder.role_title or stakeholder.stakeholder_type}）對專案需求的觀點",
            "recommended_topics": [
                {"topic": t, "reason": "受訪者專長領域", "priority": "high"}
                for t in (stakeholder.expertise_tags or [])[:3]
            ],
            "excluded_topics": [
                {"topic": t, "reason": "超出受訪者知識範圍"}
                for t in (stakeholder.knowledge_boundaries or [])[:3]
            ],
            "suggested_questions": [
                {
                    "question": c.question_text,
                    "intent": c.question_type,
                    "expected_insight": c.focus_text or "",
                }
                for c in cards[:3]
            ],
            "time_estimate_minutes": max(30, len(cards) * 3),
        }


interview_brief_service = InterviewBriefService()
