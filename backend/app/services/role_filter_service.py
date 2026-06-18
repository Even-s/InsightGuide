"""Role Filter Service - filters question cards based on stakeholder role."""

import logging
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from app.models.question_card import QuestionCard
from app.models.stakeholder_profile import StakeholderProfile
from app.models.interview_session import InterviewSession, InterviewCardState

logger = logging.getLogger(__name__)


class RoleFilterService:
    """Filter and categorize question cards by stakeholder role applicability."""

    def filter_cards_for_stakeholder(
        self,
        cards: List[QuestionCard],
        stakeholder: StakeholderProfile,
    ) -> Dict[str, List[QuestionCard]]:
        """Categorize cards by applicability for a given stakeholder.

        Priority logic:
        1. card.not_recommended_roles contains stakeholder_type → not_applicable
        2. card.target_roles specified and contains stakeholder_type → applicable
        3. card.target_roles specified but doesn't contain → uncertain
        4. card.expertise_required overlaps stakeholder.expertise_tags → applicable
        5. card.expertise_required overlaps stakeholder.knowledge_boundaries → not_applicable
        6. No role constraints → applicable (universal question)
        """
        result: Dict[str, List[QuestionCard]] = {
            "applicable": [],
            "not_applicable": [],
            "uncertain": [],
        }

        stakeholder_type = stakeholder.stakeholder_type
        expertise = set(stakeholder.expertise_tags or [])
        boundaries = set(stakeholder.knowledge_boundaries or [])

        for card in cards:
            category = self._categorize_card(card, stakeholder_type, expertise, boundaries)
            result[category].append(card)

        return result

    def _categorize_card(
        self,
        card: QuestionCard,
        stakeholder_type: str,
        expertise: set,
        boundaries: set,
    ) -> str:
        """Determine a single card's applicability category."""
        not_recommended = set(card.not_recommended_roles or [])
        target_roles = set(card.target_roles or [])
        required_expertise = set(card.expertise_required or [])

        # Rule 1: explicitly not recommended
        if stakeholder_type in not_recommended:
            return "not_applicable"

        # Rule 2 & 3: target_roles specified
        if target_roles:
            if stakeholder_type in target_roles:
                return "applicable"
            else:
                return "uncertain"

        # Rule 4 & 5: expertise matching
        if required_expertise:
            if required_expertise & expertise:
                return "applicable"
            if required_expertise & boundaries:
                return "not_applicable"
            return "uncertain"

        # Rule 6: no constraints → universal
        return "applicable"

    def apply_role_filter_to_session(
        self,
        db: Session,
        session_id: str,
    ) -> Dict[str, int]:
        """Apply role filtering to all card states in a session.

        If cards lack role targeting data, attempts to infer from
        question_type and content (fast heuristic, no AI call).
        Then marks cards as not_applicable_for_role based on stakeholder profile.

        Returns count of cards in each category.
        """
        session = db.query(InterviewSession).filter(
            InterviewSession.id == session_id
        ).first()
        if not session or not session.stakeholder_profile_id:
            return {"applicable": 0, "not_applicable": 0, "uncertain": 0, "skipped": True}

        stakeholder = db.query(StakeholderProfile).filter(
            StakeholderProfile.id == session.stakeholder_profile_id
        ).first()
        if not stakeholder:
            return {"applicable": 0, "not_applicable": 0, "uncertain": 0, "skipped": True}

        # Load all cards for this document
        cards = db.query(QuestionCard).filter(
            QuestionCard.document_id == session.document_id
        ).all()

        # Auto-infer role targeting for cards that lack it (heuristic, no AI)
        cards_needing_targeting = [c for c in cards if not c.target_roles and not c.not_recommended_roles]
        if cards_needing_targeting:
            self._infer_role_targeting_heuristic(cards_needing_targeting)
            db.flush()

        # Filter
        categorized = self.filter_cards_for_stakeholder(cards, stakeholder)

        # Update card states for not_applicable cards
        not_applicable_ids = {c.id for c in categorized["not_applicable"]}

        if not_applicable_ids:
            card_states = db.query(InterviewCardState).filter(
                InterviewCardState.session_id == session_id,
                InterviewCardState.question_card_id.in_(not_applicable_ids),
                InterviewCardState.status.in_(["pending"]),
            ).all()

            for state in card_states:
                state.status = "not_applicable_for_role"

        db.commit()

        return {
            "applicable": len(categorized["applicable"]),
            "not_applicable": len(categorized["not_applicable"]),
            "uncertain": len(categorized["uncertain"]),
            "skipped": False,
        }

    def _infer_role_targeting_heuristic(self, cards: List[QuestionCard]):
        """Fast heuristic to infer role targeting from question content.

        Uses keyword matching — no AI call. Sets target_roles and
        not_recommended_roles based on common patterns.
        """
        tech_keywords = {"api", "系統", "架構", "資料庫", "部署", "整合", "串接", "伺服器", "效能", "schema", "技術"}
        biz_keywords = {"客戶", "業務", "銷售", "流程", "痛點", "需求", "成交", "報價", "訂單"}
        mgmt_keywords = {"預算", "kpi", "決策", "目標", "時程", "roi", "策略", "優先"}

        for card in cards:
            text_lower = (card.question_text or "").lower()
            focus_lower = (card.focus_text or "").lower()
            combined = text_lower + " " + focus_lower

            has_tech = any(kw in combined for kw in tech_keywords)
            has_biz = any(kw in combined for kw in biz_keywords)
            has_mgmt = any(kw in combined for kw in mgmt_keywords)

            if has_tech and not has_biz:
                card.target_roles = ["engineering", "operations"]
                card.not_recommended_roles = ["business", "customer_support"]
                card.question_intent = "technical_constraint"
            elif has_mgmt and not has_tech:
                card.target_roles = ["management", "product"]
                card.not_recommended_roles = []
                card.question_intent = "decision_criteria"
            elif has_biz and not has_tech:
                card.target_roles = ["business", "customer_support", "operations"]
                card.not_recommended_roles = []
                card.question_intent = "business_process"
            # If mixed or unclear, leave empty (will be categorized as "applicable" for all)

    def is_card_applicable_for_stakeholder(
        self,
        card: QuestionCard,
        stakeholder: Optional[StakeholderProfile],
    ) -> bool:
        """Quick check: is this card applicable for the given stakeholder?

        Returns True if no stakeholder is set (backwards compatibility).
        """
        if not stakeholder:
            return True

        category = self._categorize_card(
            card,
            stakeholder.stakeholder_type,
            set(stakeholder.expertise_tags or []),
            set(stakeholder.knowledge_boundaries or []),
        )
        return category != "not_applicable"

    def get_card_coverage_for_project(
        self,
        db: Session,
        project_id: str,
    ) -> Dict[str, Any]:
        """Get role coverage analysis for the entire project."""
        from app.models.document import Document

        documents = db.query(Document).filter(
            Document.project_id == project_id
        ).all()
        if not documents:
            return {"total_cards": 0, "coverage_by_role": {}}

        doc_ids = [d.id for d in documents]
        cards = db.query(QuestionCard).filter(
            QuestionCard.document_id.in_(doc_ids)
        ).all()

        # Analyze which roles are needed
        role_needs: Dict[str, int] = {}
        for card in cards:
            for role in (card.target_roles or []):
                role_needs[role] = role_needs.get(role, 0) + 1

        # Check which roles have been interviewed
        from app.models.stakeholder_profile import StakeholderProfile as SP
        profiles = db.query(SP).filter(
            SP.project_id == project_id,
            SP.status == "interviewed",
        ).all()
        interviewed_roles = {p.stakeholder_type for p in profiles}

        coverage_by_role = {}
        for role, count in role_needs.items():
            coverage_by_role[role] = {
                "applicable_cards": count,
                "has_been_interviewed": role in interviewed_roles,
            }

        return {
            "total_cards": len(cards),
            "cards_with_role_targeting": len([c for c in cards if c.target_roles]),
            "coverage_by_role": coverage_by_role,
            "roles_not_yet_interviewed": [r for r in role_needs if r not in interviewed_roles],
        }


role_filter_service = RoleFilterService()
