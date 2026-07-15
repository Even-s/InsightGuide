"""Services for interview topic series and immutable interview rounds."""

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.interview_insight_memo import InterviewInsightMemo
from app.models.interview_round import InterviewRound
from app.models.interview_series import InterviewSeries
from app.models.interview_session import InterviewSession
from app.services.interview_series_service import interview_series_service
from app.services.stakeholder_card_generator import stakeholder_card_generator

GENERATION_MODES = {"continue_unfinished", "follow_up", "validate", "new_scope"}


class InterviewRoundService:
    """Coordinates series, round planning, and immutable guide generation."""

    def list_rounds(self, db: Session, series_id: str) -> List[InterviewRound]:
        interview_series_service.get_series(db, series_id)
        return (
            db.query(InterviewRound)
            .filter(InterviewRound.series_id == series_id)
            .order_by(InterviewRound.round_number.asc())
            .all()
        )

    def get_round(self, db: Session, round_id: str) -> InterviewRound:
        interview_round = db.query(InterviewRound).filter(InterviewRound.id == round_id).first()
        if not interview_round:
            raise ValueError(f"Interview round {round_id} not found")
        return interview_round

    def create_round(
        self,
        db: Session,
        series_id: str,
        *,
        objective: Optional[str] = None,
        generation_mode: str = "follow_up",
        source_session_ids: Optional[List[str]] = None,
        focus_topics: Optional[List[str]] = None,
        exclude_completed_questions: bool = True,
    ) -> InterviewRound:
        if generation_mode not in GENERATION_MODES:
            raise ValueError(f"Unsupported generation mode: {generation_mode}")

        # Serialize round-number allocation for this topic series.
        series = (
            db.query(InterviewSeries)
            .filter(InterviewSeries.id == series_id)
            .with_for_update()
            .first()
        )
        if not series:
            raise ValueError(f"Interview series {series_id} not found")

        source_ids = list(dict.fromkeys(source_session_ids or []))
        if source_ids:
            valid_count = (
                db.query(InterviewSession)
                .filter(
                    InterviewSession.id.in_(source_ids),
                    InterviewSession.project_id == series.project_id,
                    InterviewSession.stakeholder_profile_id == series.stakeholder_profile_id,
                )
                .count()
            )
            if valid_count != len(source_ids):
                raise ValueError("One or more source sessions do not belong to this stakeholder")

        max_round = (
            db.query(func.max(InterviewRound.round_number))
            .filter(InterviewRound.series_id == series_id)
            .scalar()
            or 0
        )
        interview_round = InterviewRound(
            id=f"round_{uuid.uuid4().hex[:12]}",
            series_id=series_id,
            round_number=max_round + 1,
            objective=objective,
            generation_mode=generation_mode,
            source_session_ids=source_ids,
            focus_topics=focus_topics or [],
            exclude_completed_questions=exclude_completed_questions,
            status="draft",
        )
        db.add(interview_round)
        db.commit()
        db.refresh(interview_round)
        return interview_round

    def get_or_create_editable_round(
        self,
        db: Session,
        series_id: str,
        *,
        objective: Optional[str] = None,
        focus_topics: Optional[List[str]] = None,
    ) -> InterviewRound:
        latest = (
            db.query(InterviewRound)
            .filter(InterviewRound.series_id == series_id)
            .order_by(InterviewRound.round_number.desc())
            .first()
        )
        if latest and latest.status in {"draft", "guide_ready"}:
            has_sessions = (
                db.query(InterviewSession.id)
                .filter(InterviewSession.interview_round_id == latest.id)
                .first()
                is not None
            )
            if not has_sessions:
                if objective:
                    latest.objective = objective
                if focus_topics:
                    latest.focus_topics = focus_topics
                db.commit()
                db.refresh(latest)
                return latest

        source_ids: List[str] = []
        if latest:
            source_ids = [
                session.id
                for session in (
                    db.query(InterviewSession)
                    .filter(InterviewSession.interview_round_id == latest.id)
                    .order_by(InterviewSession.created_at.desc())
                    .limit(1)
                    .all()
                )
            ]
        return self.create_round(
            db,
            series_id,
            objective=objective,
            generation_mode="follow_up" if latest else "new_scope",
            source_session_ids=source_ids,
            focus_topics=focus_topics,
            exclude_completed_questions=True,
        )

    def generate_round_guide(
        self,
        db: Session,
        round_id: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        interview_round = self.get_round(db, round_id)
        series = interview_series_service.get_series(db, interview_round.series_id)
        project, profile = interview_series_service.get_project_and_profile(
            db, series.project_id, series.stakeholder_profile_id
        )

        generation_options: Dict[str, Any] = dict(options or {})
        if not generation_options.get("interview_style"):
            generation_options["interview_style"] = {
                "continue_unfinished": "structured",
                "follow_up": "exploratory",
                "validate": "validation",
                "new_scope": "exploratory",
            }.get(interview_round.generation_mode, "exploratory")
        if interview_round.objective:
            generation_options.setdefault("interview_purpose", interview_round.objective)
        if interview_round.focus_topics:
            generation_options.setdefault("focus_topics", "、".join(interview_round.focus_topics))
            generation_options.setdefault("must_cover_topics", interview_round.focus_topics)

        source_context = self._source_context(db, interview_round.source_session_ids)
        if source_context["unresolved_questions"]:
            generation_options.setdefault(
                "reference_questions", source_context["unresolved_questions"]
            )
        if interview_round.exclude_completed_questions and source_context["covered_topics"]:
            generation_options.setdefault(
                "exclude_topics",
                "已取得充分答案，除非需要驗證請勿重複："
                + "、".join(source_context["covered_topics"]),
            )

        result = stakeholder_card_generator.generate_cards_for_stakeholder(
            db,
            project.id,
            profile.id,
            options=generation_options,
            interview_round=interview_round,
        )
        result["series_id"] = series.id
        result["round_id"] = interview_round.id
        result["round_number"] = interview_round.round_number
        return result

    @staticmethod
    def _source_context(db: Session, session_ids: List[str]) -> Dict[str, List[str]]:
        if not session_ids:
            return {"unresolved_questions": [], "covered_topics": []}
        memos = (
            db.query(InterviewInsightMemo)
            .filter(InterviewInsightMemo.session_id.in_(session_ids))
            .all()
        )
        unresolved: List[str] = []
        covered: List[str] = []
        for memo in memos:
            covered.extend(memo.topics_covered or [])
            for item in memo.unresolved_questions or []:
                question = item.get("question") if isinstance(item, dict) else str(item)
                if question:
                    unresolved.append(question)
        return {
            "unresolved_questions": list(dict.fromkeys(unresolved)),
            "covered_topics": list(dict.fromkeys(covered)),
        }


interview_round_service = InterviewRoundService()
