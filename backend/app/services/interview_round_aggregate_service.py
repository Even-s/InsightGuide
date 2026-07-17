"""Build and query canonical cumulative outputs for interview rounds."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.card_criterion_evidence import CardCriterionEvidence
from app.models.interview_insight_memo import InterviewInsightMemo
from app.models.interview_round import InterviewRound
from app.models.interview_round_aggregate import InterviewRoundAggregate
from app.models.interview_series import InterviewSeries
from app.models.interview_session import InterviewCardState, InterviewSession


class InterviewRoundAggregateService:
    """Owns invalidation and deterministic rebuilding of round outputs."""

    def get(self, db: Session, round_id: str) -> Optional[InterviewRoundAggregate]:
        return (
            db.query(InterviewRoundAggregate)
            .filter(InterviewRoundAggregate.round_id == round_id)
            .first()
        )

    def invalidate(
        self,
        db: Session,
        round_id: str,
        *,
        commit: bool = True,
    ) -> InterviewRoundAggregate:
        aggregate = self.get(db, round_id)
        now = datetime.utcnow()
        if not aggregate:
            aggregate = InterviewRoundAggregate(
                id=f"roundagg_{uuid.uuid4().hex[:12]}",
                round_id=round_id,
                status="stale",
                version=0,
                invalidated_at=now,
            )
            db.add(aggregate)
        else:
            aggregate.status = "stale"
            aggregate.invalidated_at = now
        self._invalidate_project_outputs(db, round_id)
        if commit:
            db.commit()
            db.refresh(aggregate)
        else:
            db.flush()
        return aggregate

    def rebuild(
        self,
        db: Session,
        round_id: str,
        *,
        commit: bool = True,
    ) -> InterviewRoundAggregate:
        interview_round = db.query(InterviewRound).filter(InterviewRound.id == round_id).first()
        if not interview_round:
            raise ValueError(f"Interview round {round_id} not found")

        aggregate = self.get(db, round_id)
        if not aggregate:
            aggregate = InterviewRoundAggregate(
                id=f"roundagg_{uuid.uuid4().hex[:12]}",
                round_id=round_id,
                version=0,
            )
            db.add(aggregate)

        sessions = (
            db.query(InterviewSession)
            .filter(InterviewSession.interview_round_id == round_id)
            .order_by(InterviewSession.created_at.asc(), InterviewSession.id.asc())
            .all()
        )
        session_ids = [session.id for session in sessions]
        latest_session = sessions[-1] if sessions else None
        latest_memo = (
            db.query(InterviewInsightMemo)
            .filter(
                InterviewInsightMemo.interview_round_id == round_id,
                InterviewInsightMemo.status == "completed",
            )
            .order_by(
                InterviewInsightMemo.generated_at.desc().nullslast(),
                InterviewInsightMemo.created_at.desc(),
                InterviewInsightMemo.id.desc(),
            )
            .first()
        )

        coverage_items = []
        coverage_counts: dict[str, int] = {}
        if session_ids:
            card_states = (
                db.query(InterviewCardState)
                .filter(InterviewCardState.session_id.in_(session_ids))
                .order_by(
                    InterviewCardState.updated_at.asc(),
                    InterviewCardState.created_at.asc(),
                    InterviewCardState.id.asc(),
                )
                .all()
            )
            latest_state_by_card = {}
            for state in card_states:
                latest_state_by_card[state.question_card_id] = state

            for state in sorted(
                latest_state_by_card.values(), key=lambda item: item.question_card_id
            ):
                coverage_counts[state.status] = coverage_counts.get(state.status, 0) + 1
                coverage_items.append(
                    {
                        "cardId": state.question_card_id,
                        "status": state.status,
                        "confidence": (
                            float(state.confidence) if state.confidence is not None else None
                        ),
                        "evidenceTranscript": state.evidence_transcript,
                        "evidence": state.evidence,
                        "answeredAt": state.answered_at.isoformat() if state.answered_at else None,
                        "sourceSessionId": state.session_id,
                    }
                )

        evidence_items = []
        if session_ids:
            criterion_rows = (
                db.query(CardCriterionEvidence)
                .filter(CardCriterionEvidence.session_id.in_(session_ids))
                .order_by(CardCriterionEvidence.created_at.asc())
                .all()
            )
            latest_by_criterion = {}
            for row in criterion_rows:
                latest_by_criterion[(row.card_id, row.criterion_id)] = row
            evidence_items = [
                {
                    "cardId": row.card_id,
                    "criterionId": row.criterion_id,
                    "status": row.status,
                    "evidenceQuote": row.evidence_quote,
                    "normalizedValue": row.normalized_value,
                    "confidence": (
                        float(row.evaluator_confidence)
                        if row.evaluator_confidence is not None
                        else None
                    ),
                    "sourceSessionId": row.session_id,
                }
                for row in latest_by_criterion.values()
            ]

        aggregate.latest_memo_id = latest_memo.id if latest_memo else None
        aggregate.source_session_ids = session_ids
        aggregate.coverage_snapshot = {
            "sourceSessionId": latest_session.id if latest_session else None,
            "sourceSessionIds": session_ids,
            "mergeMode": "latest_state_per_question_card",
            "counts": coverage_counts,
            "cards": coverage_items,
        }
        aggregate.evidence_snapshot = evidence_items
        aggregate.status = "ready" if latest_memo else "partial"
        aggregate.version = (aggregate.version or 0) + 1
        aggregate.generated_at = datetime.utcnow()
        aggregate.invalidated_at = None
        self._invalidate_project_outputs(db, round_id)

        if commit:
            db.commit()
            db.refresh(aggregate)
        else:
            db.flush()
        return aggregate

    def _invalidate_project_outputs(self, db: Session, round_id: str) -> None:
        """Mark every project-level derivative as stale after round data changes."""
        from app.models.brd_readiness_report import BRDReadinessReport
        from app.models.requirement_evidence_matrix import RequirementEvidenceMatrix

        project_id = (
            db.query(InterviewSeries.project_id)
            .join(InterviewRound, InterviewRound.series_id == InterviewSeries.id)
            .filter(InterviewRound.id == round_id)
            .scalar()
        )
        if not project_id:
            return

        matrix = (
            db.query(RequirementEvidenceMatrix)
            .filter(RequirementEvidenceMatrix.project_id == project_id)
            .first()
        )
        if matrix:
            matrix.status = "stale"

        db.query(BRDReadinessReport).filter(BRDReadinessReport.project_id == project_id).delete(
            synchronize_session=False
        )

    def latest_memos_for_project(
        self,
        db: Session,
        project_id: str,
    ) -> List[InterviewInsightMemo]:
        """Return exactly one current cumulative memo per ready round.

        Project-level derivatives should not scan ``InterviewInsightMemo``
        directly. They read through the ready round aggregates, whose
        ``latest_memo_id`` is the canonical pointer for cumulative round output.
        """
        return [
            aggregate.latest_memo
            for aggregate in self.ready_aggregates_for_project(db, project_id)
            if aggregate.latest_memo is not None
        ]

    def ready_aggregates_for_project(
        self,
        db: Session,
        project_id: str,
    ) -> List[InterviewRoundAggregate]:
        """Return the canonical ready aggregate rows for a project.

        BRD, Readiness and Evidence Matrix services use these aggregate rows as
        their source of truth. The joined memo is only accepted when it is the
        aggregate's latest completed memo.
        """
        return (
            db.query(InterviewRoundAggregate)
            .options(joinedload(InterviewRoundAggregate.latest_memo))
            .join(
                InterviewInsightMemo,
                InterviewRoundAggregate.latest_memo_id == InterviewInsightMemo.id,
            )
            .join(InterviewRound, InterviewRound.id == InterviewRoundAggregate.round_id)
            .join(InterviewSeries, InterviewSeries.id == InterviewRound.series_id)
            .filter(
                InterviewSeries.project_id == project_id,
                InterviewRoundAggregate.status == "ready",
                InterviewInsightMemo.status == "completed",
            )
            .order_by(
                InterviewSeries.created_at.asc(),
                InterviewRound.round_number.asc(),
                InterviewRound.created_at.asc(),
                InterviewRoundAggregate.generated_at.asc(),
                InterviewRoundAggregate.id.asc(),
            )
            .all()
        )


interview_round_aggregate_service = InterviewRoundAggregateService()
