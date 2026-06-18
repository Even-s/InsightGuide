"""
Unit tests for _reduce_state() in Answer Evaluation Engine.
Tests the deterministic state machine for card state transitions.
"""

import pytest
from app.services.answer_evaluation_engine import AnswerEvaluationEngine


class TestReduceState:
    """Test the deterministic state reducer."""

    def setup_method(self):
        self.engine = AnswerEvaluationEngine()

    def _judgment(self, confidence=0.0, is_covered=False, evidence_quote="", missing=None):
        return {
            "confidence": confidence,
            "is_covered": is_covered,
            "evidence_quote": evidence_quote,
            "missing_element_ids": missing or [],
            "covered_element_ids": [],
        }

    # --- Basic state transitions ---

    def test_zero_confidence_stays_pending(self):
        state, conf = self.engine._reduce_state("pending", self._judgment(confidence=0))
        assert state == "pending"

    def test_low_confidence_activates_listening(self):
        state, conf = self.engine._reduce_state("pending", self._judgment(confidence=0.1))
        assert state == "listening"

    def test_medium_confidence_probably_sufficient(self):
        state, conf = self.engine._reduce_state("pending", self._judgment(confidence=0.5))
        assert state == "probably_sufficient"

    def test_high_confidence_with_all_conditions_sufficient(self):
        state, conf = self.engine._reduce_state(
            "pending",
            self._judgment(confidence=0.8, is_covered=True, evidence_quote="原文", missing=[])
        )
        assert state == "sufficient"

    # --- Sufficient gating ---

    def test_high_confidence_without_evidence_not_sufficient(self):
        state, conf = self.engine._reduce_state(
            "pending",
            self._judgment(confidence=0.9, is_covered=True, evidence_quote="", missing=[])
        )
        assert state == "probably_sufficient"

    def test_high_confidence_without_is_covered_not_sufficient(self):
        state, conf = self.engine._reduce_state(
            "pending",
            self._judgment(confidence=0.9, is_covered=False, evidence_quote="有證據", missing=[])
        )
        assert state == "probably_sufficient"

    def test_high_confidence_with_missing_elements_not_sufficient(self):
        state, conf = self.engine._reduce_state(
            "pending",
            self._judgment(confidence=0.9, is_covered=True, evidence_quote="有證據", missing=["c1"])
        )
        assert state == "probably_sufficient"

    def test_confidence_below_07_not_sufficient(self):
        state, conf = self.engine._reduce_state(
            "pending",
            self._judgment(confidence=0.65, is_covered=True, evidence_quote="有", missing=[])
        )
        assert state == "probably_sufficient"

    # --- Partial transcript constraints ---

    def test_partial_cannot_reach_sufficient(self):
        state, conf = self.engine._reduce_state(
            "pending",
            self._judgment(confidence=0.9, is_covered=True, evidence_quote="有", missing=[]),
            is_partial=True
        )
        assert state == "probably_sufficient"
        assert conf <= 0.80

    def test_partial_can_reach_probably_sufficient(self):
        state, conf = self.engine._reduce_state(
            "pending",
            self._judgment(confidence=0.5),
            is_partial=True
        )
        assert state == "probably_sufficient"

    # --- State only moves forward ---

    def test_cannot_go_back_from_listening_to_pending(self):
        state, conf = self.engine._reduce_state("listening", self._judgment(confidence=0))
        assert state == "listening"

    def test_cannot_go_back_from_probably_to_listening(self):
        state, conf = self.engine._reduce_state("probably_sufficient", self._judgment(confidence=0.1))
        assert state == "probably_sufficient"

    def test_cannot_go_back_from_sufficient(self):
        state, conf = self.engine._reduce_state("sufficient", self._judgment(confidence=0))
        assert state == "sufficient"

    def test_probably_sufficient_can_advance_to_sufficient(self):
        state, conf = self.engine._reduce_state(
            "probably_sufficient",
            self._judgment(confidence=0.9, is_covered=True, evidence_quote="有", missing=[])
        )
        assert state == "sufficient"

    # --- Edge cases ---

    def test_confidence_exactly_025_is_listening(self):
        state, conf = self.engine._reduce_state("pending", self._judgment(confidence=0.25))
        assert state == "listening"

    def test_confidence_026_is_probably_sufficient(self):
        state, conf = self.engine._reduce_state("pending", self._judgment(confidence=0.26))
        assert state == "probably_sufficient"

    def test_confidence_exactly_07_with_all_conditions_sufficient(self):
        state, conf = self.engine._reduce_state(
            "pending",
            self._judgment(confidence=0.7, is_covered=True, evidence_quote="有", missing=[])
        )
        assert state == "sufficient"


class TestReduceStateAccumulation:
    """Test that probably_sufficient cards can continue accumulating."""

    def setup_method(self):
        self.engine = AnswerEvaluationEngine()

    def test_probably_sufficient_continues_with_more_evidence(self):
        state, conf = self.engine._reduce_state(
            "probably_sufficient",
            {
                "confidence": 0.6,
                "is_covered": False,
                "evidence_quote": "部分回答",
                "missing_element_ids": ["c1"],
                "covered_element_ids": ["c0"],
            }
        )
        assert state == "probably_sufficient"

    def test_listening_can_advance_to_probably_sufficient(self):
        state, conf = self.engine._reduce_state(
            "listening",
            {
                "confidence": 0.4,
                "is_covered": False,
                "evidence_quote": "",
                "missing_element_ids": ["c0"],
                "covered_element_ids": [],
            }
        )
        assert state == "probably_sufficient"
