"""
Unit tests for Answer Completion Scorer.
Tests deterministic scoring logic from criterion evaluations.
"""

import pytest

from app.services.answer_completion_scorer import AnswerCompletionScorer, answer_completion_scorer


class TestCalculateCompletion:
    """Test weighted completion score calculation."""

    def test_empty_inputs_return_zero(self):
        assert answer_completion_scorer.calculate_completion([], []) == 0.0
        assert answer_completion_scorer.calculate_completion([], [{"criterion_id": "c1"}]) == 0.0
        assert answer_completion_scorer.calculate_completion([{"id": "c1"}], []) == 0.0

    def test_all_satisfied_returns_one(self):
        criteria = [
            {"id": "c0", "weight": 0.5},
            {"id": "c1", "weight": 0.5},
        ]
        evals = [
            {"criterion_id": "c0", "status": "satisfied", "evidence_quotes": ["quote"]},
            {"criterion_id": "c1", "status": "satisfied", "evidence_quotes": ["quote"]},
        ]
        assert answer_completion_scorer.calculate_completion(criteria, evals) == 1.0

    def test_all_not_addressed_returns_zero(self):
        criteria = [
            {"id": "c0", "weight": 0.5},
            {"id": "c1", "weight": 0.5},
        ]
        evals = [
            {"criterion_id": "c0", "status": "not_addressed"},
            {"criterion_id": "c1", "status": "not_addressed"},
        ]
        assert answer_completion_scorer.calculate_completion(criteria, evals) == 0.0

    def test_partially_satisfied_scores_half(self):
        criteria = [{"id": "c0", "weight": 1.0}]
        evals = [{"criterion_id": "c0", "status": "partially_satisfied"}]
        assert answer_completion_scorer.calculate_completion(criteria, evals) == 0.5

    def test_mixed_statuses_weighted(self):
        criteria = [
            {"id": "c0", "weight": 0.5},
            {"id": "c1", "weight": 0.5},
        ]
        evals = [
            {"criterion_id": "c0", "status": "satisfied", "evidence_quotes": ["q"]},
            {"criterion_id": "c1", "status": "not_addressed"},
        ]
        assert answer_completion_scorer.calculate_completion(criteria, evals) == 0.5

    def test_not_applicable_excluded_from_weight(self):
        criteria = [
            {"id": "c0", "weight": 0.5},
            {"id": "c1", "weight": 0.5},
        ]
        evals = [
            {"criterion_id": "c0", "status": "satisfied", "evidence_quotes": ["q"]},
            {"criterion_id": "c1", "status": "not_applicable"},
        ]
        # c1 excluded, only c0 counts → 1.0
        assert answer_completion_scorer.calculate_completion(criteria, evals) == 1.0

    def test_satisfied_without_evidence_downgraded(self):
        criteria = [{"id": "c0", "weight": 1.0}]
        evals = [{"criterion_id": "c0", "status": "satisfied", "evidence_quotes": []}]
        # Downgraded to 0.5 (partial) because no evidence
        assert answer_completion_scorer.calculate_completion(criteria, evals) == 0.5

    def test_contradicted_scores_zero(self):
        criteria = [{"id": "c0", "weight": 1.0}]
        evals = [{"criterion_id": "c0", "status": "contradicted"}]
        assert answer_completion_scorer.calculate_completion(criteria, evals) == 0.0

    def test_missing_evaluation_for_criterion_scores_zero(self):
        criteria = [
            {"id": "c0", "weight": 0.5},
            {"id": "c1", "weight": 0.5},
        ]
        evals = [
            {"criterion_id": "c0", "status": "satisfied", "evidence_quotes": ["q"]},
            # c1 has no evaluation
        ]
        # c0=1.0*0.5, c1=0.0*0.5 → 0.5
        assert answer_completion_scorer.calculate_completion(criteria, evals) == 0.5

    def test_unequal_weights(self):
        criteria = [
            {"id": "c0", "weight": 0.8},
            {"id": "c1", "weight": 0.2},
        ]
        evals = [
            {"criterion_id": "c0", "status": "satisfied", "evidence_quotes": ["q"]},
            {"criterion_id": "c1", "status": "not_addressed"},
        ]
        # (0.8*1.0 + 0.2*0.0) / 1.0 = 0.8
        assert answer_completion_scorer.calculate_completion(criteria, evals) == 0.8

    def test_default_weight_is_one(self):
        criteria = [{"id": "c0"}, {"id": "c1"}]  # no weight specified
        evals = [
            {"criterion_id": "c0", "status": "satisfied", "evidence_quotes": ["q"]},
            {"criterion_id": "c1", "status": "satisfied", "evidence_quotes": ["q"]},
        ]
        assert answer_completion_scorer.calculate_completion(criteria, evals) == 1.0


class TestIsSufficient:
    """Test sufficiency gating logic."""

    def _make_criteria(self, critical=True, required=True):
        return [{"id": "c0", "weight": 1.0, "critical": critical, "required": required}]

    def _make_eval(self, status="satisfied", evidence=True):
        return [
            {"criterion_id": "c0", "status": status, "evidence_quotes": ["q"] if evidence else []}
        ]

    def test_sufficient_when_all_gates_pass(self):
        criteria = self._make_criteria()
        evals = self._make_eval()
        assert answer_completion_scorer.is_sufficient(criteria, evals, 0.9) is True

    def test_fails_on_low_completion_score(self):
        criteria = self._make_criteria()
        evals = self._make_eval()
        assert answer_completion_scorer.is_sufficient(criteria, evals, 0.7) is False

    def test_fails_on_contradicted_criterion(self):
        criteria = [{"id": "c0", "weight": 1.0, "critical": True, "required": True}]
        evals = [{"criterion_id": "c0", "status": "contradicted", "evidence_quotes": ["q"]}]
        assert answer_completion_scorer.is_sufficient(criteria, evals, 0.9) is False

    def test_fails_on_critical_not_satisfied(self):
        criteria = self._make_criteria(critical=True, required=True)
        evals = self._make_eval(status="partially_satisfied")
        assert answer_completion_scorer.is_sufficient(criteria, evals, 0.9) is False

    def test_fails_on_satisfied_without_evidence(self):
        criteria = self._make_criteria()
        evals = self._make_eval(evidence=False)
        assert answer_completion_scorer.is_sufficient(criteria, evals, 0.9) is False

    def test_non_critical_partial_can_still_be_sufficient(self):
        criteria = [
            {"id": "c0", "weight": 0.9, "critical": True, "required": True},
            {"id": "c1", "weight": 0.1, "critical": False, "required": False},
        ]
        evals = [
            {"criterion_id": "c0", "status": "satisfied", "evidence_quotes": ["q"]},
            {"criterion_id": "c1", "status": "partially_satisfied", "evidence_quotes": []},
        ]
        # c0 satisfied with evidence, c1 is not critical — should pass
        assert answer_completion_scorer.is_sufficient(criteria, evals, 0.9) is True

    def test_multiple_criteria_all_must_pass(self):
        criteria = [
            {"id": "c0", "weight": 0.5, "critical": True, "required": True},
            {"id": "c1", "weight": 0.5, "critical": True, "required": True},
        ]
        evals = [
            {"criterion_id": "c0", "status": "satisfied", "evidence_quotes": ["q"]},
            {"criterion_id": "c1", "status": "not_addressed", "evidence_quotes": []},
        ]
        assert answer_completion_scorer.is_sufficient(criteria, evals, 0.9) is False


class TestDetermineState:
    """Test state mapping from scores."""

    def test_sufficient_when_is_sufficient(self):
        assert answer_completion_scorer.determine_state(0.9, True, True) == "sufficient"

    def test_high_score_not_sufficient_is_probably(self):
        assert (
            answer_completion_scorer.determine_state(0.6, False, True)
            == "probably_sufficient"
        )

    def test_low_score_with_response_is_listening(self):
        assert answer_completion_scorer.determine_state(0.2, False, True) == "listening"

    def test_zero_score_no_response_is_pending(self):
        assert answer_completion_scorer.determine_state(0.0, False, False) == "pending"

    def test_zero_score_with_response_is_listening(self):
        assert answer_completion_scorer.determine_state(0.0, False, True) == "listening"


class TestGetMissingCriteria:
    """Test missing criteria identification."""

    def test_all_satisfied_returns_empty(self):
        criteria = [{"id": "c0"}, {"id": "c1"}]
        evals = [
            {"criterion_id": "c0", "status": "satisfied"},
            {"criterion_id": "c1", "status": "satisfied"},
        ]
        assert answer_completion_scorer.get_missing_criteria(criteria, evals) == []

    def test_not_addressed_returned(self):
        criteria = [{"id": "c0"}, {"id": "c1"}]
        evals = [
            {"criterion_id": "c0", "status": "satisfied"},
            {"criterion_id": "c1", "status": "not_addressed"},
        ]
        result = answer_completion_scorer.get_missing_criteria(criteria, evals)
        assert len(result) == 1
        assert result[0]["id"] == "c1"

    def test_partially_satisfied_returned(self):
        criteria = [{"id": "c0"}]
        evals = [{"criterion_id": "c0", "status": "partially_satisfied"}]
        result = answer_completion_scorer.get_missing_criteria(criteria, evals)
        assert len(result) == 1

    def test_attempted_but_unresolved_returned(self):
        criteria = [{"id": "c0"}]
        evals = [{"criterion_id": "c0", "status": "attempted_but_unresolved"}]
        result = answer_completion_scorer.get_missing_criteria(criteria, evals)
        assert len(result) == 1

    def test_missing_evaluation_returned(self):
        criteria = [{"id": "c0"}, {"id": "c1"}]
        evals = [{"criterion_id": "c0", "status": "satisfied"}]
        result = answer_completion_scorer.get_missing_criteria(criteria, evals)
        assert len(result) == 1
        assert result[0]["id"] == "c1"

    def test_not_applicable_not_returned(self):
        criteria = [{"id": "c0"}]
        evals = [{"criterion_id": "c0", "status": "not_applicable"}]
        result = answer_completion_scorer.get_missing_criteria(criteria, evals)
        assert len(result) == 0
