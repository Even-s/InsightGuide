"""Card state reduction logic for determining state transitions."""

from typing import Any, Dict, Optional

# Question-only statuses that produce zero completion
_QUESTION_ONLY_STATUSES = frozenset(
    [
        "question_only",
        "not_yet",
        "not_started",
        "clarification_question",
    ]
)


def reduce_card_state(current_status: str, judgment: dict) -> tuple[str, float, float]:
    """Deterministic state reducer using activation/completion separation.

    Returns (new_status, activation_score, completion_score).

    activation_score: Is this card's topic being discussed? (0 or 1)
    completion_score: How much of the criteria are answered? (0.0–1.0)

    State mapping:
    - activation=0, completion=0 → pending
    - activation>0, completion=0 → listening (card glows, progress=0%)
    - activation>0, completion>0 → probably_sufficient (progress bar)
    - all gates met → sufficient

    Args:
        current_status: Current card state status
        judgment: AI judgment dict with confidence, is_covered, relation, response_status, etc.
    Returns:
        Tuple of (new_status, activation_score, completion_score)
    """
    raw_confidence = judgment.get("sufficiency_score", None) or judgment.get("confidence", 0.0)
    is_covered = judgment.get("is_sufficient", None) or judgment.get("is_covered", False)
    has_evidence = bool(judgment.get("evidence_quote"))
    missing = judgment.get("missing_element_ids", [])
    response_status = judgment.get("response_status", "not_yet")
    relation = judgment.get("relation", "irrelevant")

    # Determine activation (topic detected?)
    is_activated = (
        raw_confidence > 0
        or relation in ("answer", "tangential", "topic_mention")
        or response_status == "question_only"
    )
    activation_score = 1.0 if is_activated else 0.0

    # Determine completion (real answer evidence?)
    completion_score = raw_confidence

    # Question-only / non-answer turns: zero completion regardless of GPT score
    if response_status in _QUESTION_ONLY_STATUSES:
        completion_score = 0.0

    # Determine target state from activation + completion
    if completion_score <= 0 and activation_score <= 0:
        target = "pending"
    elif completion_score <= 0:
        target = "listening"
    elif completion_score < 0.7:
        target = "probably_sufficient"
    elif is_covered and has_evidence and not missing:
        target = "sufficient"
    else:
        target = "probably_sufficient"

    if not has_evidence and target == "sufficient":
        target = "probably_sufficient"

    # State can only move forward
    STATE_ORDER = {"pending": 0, "listening": 1, "probably_sufficient": 2, "sufficient": 3}
    current_order = STATE_ORDER.get(current_status, 0)
    target_order = STATE_ORDER.get(target, 0)

    if target_order < current_order:
        target = current_status

    return target, activation_score, completion_score


def preserve_existing_followup_when_empty(
    existing_evidence: Optional[Dict[str, Any]],
    judgment: Dict[str, Any],
) -> Dict[str, Any]:
    """Keep the last useful follow-up when a later judgment returns an empty one.

    Args:
        existing_evidence: Previous evidence dict that may contain a followup
        judgment: New judgment dict to check for followup

    Returns:
        Updated judgment dict with preserved followup if necessary
    """
    next_followup = judgment.get("suggested_followup") or judgment.get("suggestedFollowup") or ""
    if isinstance(next_followup, str) and next_followup.strip():
        return judgment

    if not isinstance(existing_evidence, dict):
        return judgment

    previous_followup = (
        existing_evidence.get("suggested_followup")
        or existing_evidence.get("suggestedFollowup")
        or ""
    )
    previous_judgment = existing_evidence.get("judgment")
    if not previous_followup and isinstance(previous_judgment, dict):
        previous_followup = (
            previous_judgment.get("suggested_followup")
            or previous_judgment.get("suggestedFollowup")
            or ""
        )

    if isinstance(previous_followup, str) and previous_followup.strip():
        return {
            **judgment,
            "suggested_followup": previous_followup.strip(),
        }

    return judgment
