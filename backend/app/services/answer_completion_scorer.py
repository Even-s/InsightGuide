"""Answer Completion Scorer - Deterministic scoring from criterion evaluations."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Deterministic status scores
STATUS_SCORE = {
    "satisfied": 1.0,
    "partially_satisfied": 0.5,
    "attempted_but_unresolved": 0.0,
    "not_addressed": 0.0,
    "contradicted": 0.0,
    "not_applicable": None,  # excluded from calculation
}


class AnswerCompletionScorer:
    """Calculates completion scores from criterion evaluations using deterministic logic."""

    def calculate_completion(
        self,
        criteria: List[Dict[str, Any]],
        criterion_evaluations: List[Dict[str, Any]],
    ) -> float:
        """Calculate weighted completion score from criterion evaluations.

        Args:
            criteria: The rubric criteria definitions (from coverage_rule)
            criterion_evaluations: The AI's per-criterion evaluation results

        Returns:
            Completion score between 0.0 and 1.0
        """
        if not criteria or not criterion_evaluations:
            return 0.0

        eval_by_id = {e["criterion_id"]: e for e in criterion_evaluations}

        total_weight = 0.0
        weighted_score = 0.0

        for criterion in criteria:
            crit_id = criterion["id"]
            weight = criterion.get("weight", 1.0)

            evaluation = eval_by_id.get(crit_id)
            if not evaluation:
                total_weight += weight
                continue

            status = evaluation.get("status", "not_addressed")
            score = STATUS_SCORE.get(status)

            if score is None:  # not_applicable - skip
                continue

            # Penalize satisfied without evidence
            if status == "satisfied" and not evaluation.get("evidence_quotes"):
                score = 0.5  # Downgrade to partial if no evidence

            total_weight += weight
            weighted_score += weight * score

        if total_weight == 0:
            return 0.0

        return weighted_score / total_weight

    def is_sufficient(
        self,
        criteria: List[Dict[str, Any]],
        criterion_evaluations: List[Dict[str, Any]],
        completion_score: float,
    ) -> bool:
        """Determine if the answer is sufficient based on strict gating rules.

        Sufficient requires ALL of:
        1. completion_score >= 0.85
        2. All critical+required criteria are "satisfied"
        3. No criterion is "contradicted"
        4. All "satisfied" criteria have evidence_quotes

        Args:
            criteria: The rubric criteria definitions
            criterion_evaluations: The AI's per-criterion evaluation results
            completion_score: Pre-calculated completion score

        Returns:
            True if the answer meets all sufficiency gates
        """
        if completion_score < 0.85:
            return False

        eval_by_id = {e["criterion_id"]: e for e in criterion_evaluations}

        for evaluation in criterion_evaluations:
            # Gate: no contradictions allowed
            if evaluation.get("status") == "contradicted":
                return False

        for criterion in criteria:
            crit_id = criterion["id"]
            is_required = criterion.get("required", False)
            is_critical = criterion.get("critical", False)

            evaluation = eval_by_id.get(crit_id)

            # Critical + required criteria must be satisfied
            if is_critical and is_required:
                if not evaluation or evaluation.get("status") != "satisfied":
                    return False
                # Must have evidence
                if not evaluation.get("evidence_quotes"):
                    return False

        # All satisfied criteria must have evidence
        for evaluation in criterion_evaluations:
            if evaluation.get("status") == "satisfied":
                if not evaluation.get("evidence_quotes"):
                    return False

        return True

    def determine_state(
        self,
        completion_score: float,
        is_sufficient: bool,
        has_response: bool,
    ) -> str:
        """Map completion score to card state.

        Args:
            completion_score: The weighted completion score (0-1)
            is_sufficient: Whether sufficiency gates are met
            has_response: Whether the participant has provided relevant content
        Returns:
            Card state string
        """
        if is_sufficient:
            return "sufficient"

        if completion_score >= 0.5:
            return "probably_sufficient"

        if completion_score > 0 or has_response:
            return "listening"

        return "pending"

    def get_missing_criteria(
        self,
        criteria: List[Dict[str, Any]],
        criterion_evaluations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Return criteria that still need to be addressed.

        Returns criteria where status is not_addressed, attempted_but_unresolved,
        or partially_satisfied.
        """
        eval_by_id = {e["criterion_id"]: e for e in criterion_evaluations}
        missing = []

        for criterion in criteria:
            crit_id = criterion["id"]
            evaluation = eval_by_id.get(crit_id)

            if not evaluation:
                missing.append(criterion)
                continue

            status = evaluation.get("status", "not_addressed")
            if status in ("not_addressed", "attempted_but_unresolved", "partially_satisfied"):
                missing.append(criterion)

        return missing


# Singleton instance
answer_completion_scorer = AnswerCompletionScorer()
