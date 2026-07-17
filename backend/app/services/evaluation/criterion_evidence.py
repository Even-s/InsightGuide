"""Criterion evidence persistence and retrieval for answer evaluation."""

import uuid
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session


def persist_criterion_evidence(
    db: Session,
    session_id: str,
    card_id: str,
    criterion_evaluations: List[Dict[str, Any]],
    utterance_id: str,
    utterance_text: str,
    model: str,
    evaluation_seq: int,
) -> None:
    """Write criterion-level evidence to the append-only ledger.

    Args:
        db: Database session
        session_id: Interview session ID
        card_id: Question card ID
        criterion_evaluations: List of criterion evaluation dicts
        utterance_id: Source utterance ID (may be temporary for partial transcripts)
        utterance_text: Utterance text for audit trail
        model: AI model used for evaluation
        evaluation_seq: Sequence number for this evaluation
    """
    from app.models.card_criterion_evidence import CardCriterionEvidence

    skip_statuses = {"not_addressed"}
    for crit_eval in criterion_evaluations:
        status = crit_eval.get("status", "not_addressed")
        if status in skip_statuses:
            continue
        evidence = CardCriterionEvidence(
            id=f"cev_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            card_id=card_id,
            criterion_id=crit_eval.get("criterion_id", ""),
            utterance_id=utterance_id,
            evaluation_turn_text=utterance_text[:500] if utterance_text else None,
            status=status,
            evidence_quote=(crit_eval.get("evidence_quotes") or [None])[0],
            normalized_value=crit_eval.get("normalized_value"),
            evaluator_confidence=crit_eval.get("evaluator_confidence"),
            reason=crit_eval.get("reason"),
            model=model,
            evaluation_seq=evaluation_seq,
            created_at=datetime.utcnow(),
        )
        db.add(evidence)


def load_existing_evidence(
    db: Session,
    session_id: str,
    card_id: str,
) -> Dict[str, str]:
    """Load best evidence status per criterion from ledger.

    Returns {criterion_id: best_status} where best_status is determined by
    the highest ranking status across all evidence entries.

    Args:
        db: Database session
        session_id: Interview session ID
        card_id: Question card ID

    Returns:
        Dict mapping criterion_id to best status string
    """
    from app.models.card_criterion_evidence import CardCriterionEvidence

    rows = (
        db.query(CardCriterionEvidence)
        .filter(
            CardCriterionEvidence.session_id == session_id,
            CardCriterionEvidence.card_id == card_id,
        )
        .order_by(CardCriterionEvidence.evaluation_seq.desc())
        .all()
    )

    STATUS_RANK = {
        "satisfied": 5,
        "partially_satisfied": 4,
        "attempted_but_unresolved": 3,
        "contradicted": 2,
        "not_applicable": 1,
        "not_addressed": 0,
    }

    best: Dict[str, str] = {}
    for row in rows:
        crit_id = row.criterion_id
        if crit_id not in best:
            best[crit_id] = row.status
        else:
            if STATUS_RANK.get(row.status, 0) > STATUS_RANK.get(best[crit_id], 0):
                best[crit_id] = row.status
    return best


def derive_state_from_ledger(
    db: Session,
    session_id: str,
    card_id: str,
    rubric_criteria: List[Dict[str, Any]],
) -> tuple:
    """Derive card state from evidence ledger using deterministic scorer.

    Returns (state, completion_score).

    Args:
        db: Database session
        session_id: Interview session ID
        card_id: Question card ID
        rubric_criteria: List of rubric criteria dicts
    Returns:
        Tuple of (state_string, completion_score)
    """
    from app.services.answer_completion_scorer import answer_completion_scorer

    evidence_statuses = load_existing_evidence(db, session_id, card_id)
    if not evidence_statuses:
        return ("pending", 0.0)

    # Build criterion_evaluations structure for the scorer
    criterion_evaluations = []
    for crit in rubric_criteria:
        crit_id = crit.get("id", "")
        status = evidence_statuses.get(crit_id, "not_addressed")
        criterion_evaluations.append(
            {
                "criterion_id": crit_id,
                "status": status,
                "evidence_quotes": ["(from ledger)"] if status == "satisfied" else [],
            }
        )

    completion_score = answer_completion_scorer.calculate_completion(
        rubric_criteria, criterion_evaluations
    )
    is_sufficient = answer_completion_scorer.is_sufficient(
        rubric_criteria, criterion_evaluations, completion_score
    )
    has_response = any(
        e["status"] not in ("not_addressed", "not_applicable") for e in criterion_evaluations
    )

    state = answer_completion_scorer.determine_state(
        completion_score, is_sufficient, has_response
    )
    return (state, completion_score)
