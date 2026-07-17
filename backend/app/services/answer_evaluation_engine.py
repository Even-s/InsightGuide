"""Answer Evaluation Engine - Core service for evaluating answer sufficiency."""

import logging
import uuid
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.card_coverage_evaluation import CardCoverageEvaluation
from app.models.interview_session import InterviewCardState
from app.models.live_utterance import LiveUtterance
from app.models.question_card import QuestionCard
from app.services.answer_completion_scorer import answer_completion_scorer
from app.services.evaluation import (
    derive_state_from_ledger,
    is_question_like,
    load_existing_evidence,
    persist_criterion_evidence,
    preserve_existing_followup_when_empty,
    reduce_card_state,
    should_skip_utterance,
)
from app.services.interview_service import interview_service
from app.services.question_card_service import question_card_service
from app.services.question_rubric_service import question_rubric_service

logger = logging.getLogger(__name__)


class AnswerEvaluationEngine:
    """
    Core engine for evaluating answer sufficiency against question cards.

    Implements two-stage evaluation:
    1. Fast candidate recall using embeddings
    2. Deep semantic judgment using AI models to determine answer sufficiency
    """

    def __init__(self):
        """Initialize answer evaluation engine."""
        pass

    def _get_next_evaluation_seq(self, db: Session, session_id: str, card_id: str) -> int:
        """Get the next evaluation sequence number for a card in a session."""
        max_seq = (
            db.query(CardCoverageEvaluation)
            .filter(
                CardCoverageEvaluation.session_id == session_id,
                CardCoverageEvaluation.card_id == card_id,
            )
            .with_entities(CardCoverageEvaluation.evaluation_seq)
            .order_by(CardCoverageEvaluation.evaluation_seq.desc())
            .first()
        )

        return (max_seq[0] + 1) if max_seq else 1

    def _get_required_element_ids(self, card: QuestionCard) -> List[str]:
        """Return canonical element IDs that drive answer sufficiency.

        mustMentionElements are the visible "important elements" in interview mode.
        semanticAnchors are matching hints that normalize into at most three
        element IDs for scoring.
        """
        coverage_rule = question_card_service.normalize_coverage_rule_for_important_elements(
            getattr(card, "coverage_rule", None) or {}
        )
        semantic_anchors = coverage_rule.get("semanticAnchors", []) or []
        must_mention_elements = coverage_rule.get("mustMentionElements", []) or []

        element_ids = [
            f"element_{index}" for index, element in enumerate(must_mention_elements) if element
        ]
        if element_ids:
            return element_ids

        return [f"anchor_{index}" for index, anchor in enumerate(semantic_anchors) if anchor]

    def _canonicalize_element_ids(self, card: QuestionCard, element_ids: set[str]) -> set[str]:
        """Map AI-returned anchor IDs into the canonical completion ID space."""
        coverage_rule = question_card_service.normalize_coverage_rule_for_important_elements(
            getattr(card, "coverage_rule", None) or {}
        )
        must_mention_elements = coverage_rule.get("mustMentionElements", []) or []
        element_count = len([element for element in must_mention_elements if element])
        required_element_ids = set(self._get_required_element_ids(card))
        if not required_element_ids:
            return set(element_ids)

        canonical_ids: set[str] = set()
        for element_id in element_ids:
            if element_id in required_element_ids:
                canonical_ids.add(element_id)
                continue

            if element_count and element_id.startswith("anchor_"):
                try:
                    index = int(element_id.split("_", 1)[1])
                except (IndexError, ValueError):
                    continue
                mapped_id = f"element_{index % element_count}"
                if mapped_id in required_element_ids:
                    canonical_ids.add(mapped_id)

        return canonical_ids

    def _normalize_completion_element_ids(
        self,
        card: QuestionCard,
        completion: Dict[str, Any],
    ) -> tuple[List[str], List[str]]:
        """Keep AI completion percentage and element IDs internally consistent."""
        required_element_ids = set(self._get_required_element_ids(card))
        covered_element_ids = self._canonicalize_element_ids(
            card, set(completion.get("covered_element_ids", []) or [])
        )
        missing_element_ids = self._canonicalize_element_ids(
            card, set(completion.get("missing_element_ids", []) or [])
        )

        if not required_element_ids:
            return sorted(covered_element_ids), sorted(missing_element_ids - covered_element_ids)

        # Only keep elements that are explicitly in covered_element_ids AND exist in required_element_ids
        covered_element_ids &= required_element_ids
        missing_element_ids = required_element_ids - covered_element_ids

        return sorted(covered_element_ids), sorted(missing_element_ids)

    def process_utterance(
        self,
        db: Session,
        session_id: str,
        utterance_id: str,
        utterance_text: str,
        theme_id: str,
        asked_card_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process a new role-neutral Realtime utterance.

        Realtime transcripts no longer assign participant roles.
        Routing is therefore based on utterance function: question-like text
        suggests related cards, while answer-like text may add evidence only
        to cards that have already been confirmed by a human.
        """
        try:
            if should_skip_utterance(utterance_text):
                logger.info(
                    f"Skipping trivial utterance for session={session_id}: '{utterance_text[:30]}'"
                )
                return []

            logger.info(
                f"Processing utterance for session={session_id}, "
                f"theme={theme_id}, text='{utterance_text[:50]}...'"
            )

            explicit_card_ids = self._normalize_card_ids(asked_card_ids)

            # The frontend-provided cards are explicit routing decisions and
            # must win over heuristic utterance classification. This prevents
            # question wording such as "通常會...？" from being evaluated as
            # an answer merely because it contains an answer-like marker.
            if explicit_card_ids or is_question_like(utterance_text):
                return self._route_question_to_card(
                    db,
                    session_id,
                    utterance_id,
                    utterance_text,
                    theme_id,
                    explicit_card_ids,
                )
            else:
                return self._evaluate_answer(db, session_id, utterance_id, utterance_text, theme_id)

        except Exception as e:
            logger.error(f"Error processing utterance: {str(e)}", exc_info=True)
            db.rollback()
            return []

    def _normalize_card_ids(
        self,
        card_ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Return unique, non-empty card ids while preserving order."""
        normalized: List[str] = []
        for card_id in card_ids or []:
            if not card_id or card_id in normalized:
                continue
            normalized.append(card_id)
        return normalized

    def _route_question_to_card(
        self,
        db: Session,
        session_id: str,
        utterance_id: str,
        utterance_text: str,
        theme_id: str,
        asked_card_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Suggest one or more related cards for a question-like utterance.

        AI question routing is advisory only. It must not activate cards or
        change the current card; a human confirmation via /active-card is
        required before transcripts are attributed to that card.
        """
        explicit_card_ids = self._normalize_card_ids(asked_card_ids)

        # Find target cards
        if explicit_card_ids:
            target_candidates = [
                {
                    "cardId": card_id,
                    "score": 1.0,
                    "status": "pending",
                    "source": "frontend",
                }
                for card_id in explicit_card_ids[:3]
            ]
            logger.info(
                "Question routing: using frontend-provided askedCardIds=%s",
                explicit_card_ids[:3],
            )
        else:
            target_candidates = self.find_candidate_cards(
                db, session_id, theme_id, utterance_text, top_k=3
            )
            best_score = (
                float(target_candidates[0].get("score", 0) or 0) if target_candidates else 0
            )
            threshold = max(0.5, best_score * 0.65)
            target_candidates = [
                candidate
                for candidate in target_candidates
                if float(candidate.get("score", 0) or 0) >= threshold
            ][:3]
            logger.info(
                "Question routing: router suggested targets=%s",
                [candidate.get("cardId") for candidate in target_candidates],
            )

        if not target_candidates:
            logger.info("Question routing: no matching card found")
            return []

        updates: List[Dict[str, Any]] = []
        for target_candidate in target_candidates:
            target_card_id = target_candidate["cardId"]
            card_state = (
                db.query(InterviewCardState)
                .filter(
                    InterviewCardState.session_id == session_id,
                    InterviewCardState.question_card_id == target_card_id,
                )
                .first()
            )

            if not card_state:
                logger.info(f"Question routing: no card state for {target_card_id}")
                continue

            # Don't re-route already completed cards
            if card_state.status in ("sufficient", "covered", "manually_checked"):
                continue

            card = db.query(QuestionCard).filter(QuestionCard.id == target_card_id).first()
            if not card:
                continue

            old_status = card_state.status

            updates.append(
                {
                    "card_id": card.id,
                    "card_state_id": card_state.id,
                    "old_status": old_status,
                    "new_status": old_status,
                    "confidence": float(target_candidate.get("score", 0) or 0),
                    "activation_score": 0.0,
                    "completion_score": (
                        float(card_state.completion_score or 0)
                        if card_state.completion_score is not None
                        else 0.0
                    ),
                    "evidence": card_state.evidence,
                    "evidence_transcript": card_state.evidence_transcript,
                    "judgment": {"response_status": "question_only", "suggested_followup": ""},
                    "evaluation_seq": None,
                    "question_suggested": True,
                    "suggestion_score": float(target_candidate.get("score", 0) or 0),
                    "suggestion_source": target_candidate.get("source", "router"),
                }
            )

        return updates

    def _find_matching_card_ids(
        self,
        db: Session,
        session_id: str,
        theme_id: str,
        question_text: str,
        top_k: int = 3,
    ) -> List[str]:
        """Find one primary card plus close related cards for a question-like utterance."""
        candidates = self.find_candidate_cards(db, session_id, theme_id, question_text, top_k=top_k)
        if not candidates:
            return []

        best_score = float(candidates[0].get("score", 0) or 0)
        threshold = max(0.5, best_score * 0.65)
        return [
            candidate["cardId"]
            for candidate in candidates
            if float(candidate.get("score", 0) or 0) >= threshold
        ][:top_k]

    def _find_best_matching_card(
        self,
        db: Session,
        session_id: str,
        theme_id: str,
        question_text: str,
    ) -> Optional[str]:
        """Find which card a question is about using text similarity. No state bonus."""
        candidates = self._load_candidate_cards(
            db,
            session_id,
            theme_id,
            statuses=["pending", "listening", "probably_sufficient", "at_risk"],
        )
        if not candidates:
            return None

        text_lower = question_text.lower()
        best_score = 0.0
        best_card_id = None

        for card_data in candidates:
            card = card_data["card"]
            score = self._score_question_route(text_lower, card)

            if score > best_score:
                best_score = score
                best_card_id = card.id

        if best_score < 0.5:
            return None

        return best_card_id

    def find_candidate_cards(
        self,
        db: Session,
        session_id: str,
        theme_id: str,
        question_text: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Public: find top-K candidate cards for a question. Returns scored list."""
        candidates = self._load_candidate_cards(
            db,
            session_id,
            theme_id,
            statuses=["pending", "listening", "probably_sufficient", "at_risk"],
        )
        if not candidates:
            return []

        text_lower = question_text.lower()
        scored = []

        for card_data in candidates:
            card = card_data["card"]
            score = self._score_question_route(text_lower, card)

            if score > 0.3:
                scored.append((score, card_data))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "cardId": card_data["card"].id,
                "questionText": card_data["card"].question_text,
                "focusText": card_data["card"].focus_text or "",
                "score": round(score, 2),
                "status": card_data["state"].status if card_data.get("state") else "pending",
            }
            for score, card_data in scored[:top_k]
        ]

    def _evaluate_answer(
        self,
        db: Session,
        session_id: str,
        utterance_id: str,
        utterance_text: str,
        theme_id: str,
    ) -> List[Dict[str, Any]]:
        """Evaluate role-neutral content for one or more related cards."""
        from app.models.interview_session import InterviewSession

        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        active_card_id = session.active_card_id if session else None
        active_source = session.active_card_source if session else None

        manual_selection_sources = {
            "user_confirmed",
            "manual_selected",
            "human_confirmed_ai_suggestion",
        }
        is_manual_selection = bool(active_card_id) and active_source in manual_selection_sources

        # If no card has been confirmed by a human yet, keep a short replay
        # buffer. This lets the facilitator confirm an AI suggestion a moment
        # late without losing the answer segment, while avoiding unlimited
        # attribution of older small talk to the next selected card.
        if not is_manual_selection and session:
            buffer = session.pending_answer_buffer or []
            buffer.append(utterance_id)
            session.pending_answer_buffer = buffer[-5:]
            db.commit()
            logger.info(
                f"Buffered utterance {utterance_id} "
                f"(waiting for card confirmation, buffer={len(session.pending_answer_buffer)})"
            )
            return []

        primary_card_id = active_card_id if is_manual_selection else None
        candidate_cards = self._load_candidate_cards(
            db,
            session_id,
            theme_id,
            statuses=["listening", "probably_sufficient", "at_risk"],
        )
        if not candidate_cards:
            logger.info("No candidate cards found for answer; skipping")
            return []

        filtered_candidates = self._prefilter_candidates(utterance_text, candidate_cards)

        if primary_card_id and not any(
            c["card"].id == primary_card_id for c in filtered_candidates
        ):
            primary_card = next(
                (c for c in candidate_cards if c["card"].id == primary_card_id),
                None,
            )
            if primary_card:
                filtered_candidates.insert(0, primary_card)

        deduped_candidates = []
        seen_card_ids = set()
        for candidate in filtered_candidates:
            card_id = candidate["card"].id
            if card_id in seen_card_ids:
                continue
            seen_card_ids.add(card_id)
            deduped_candidates.append(candidate)

        filtered_candidates = [
            c
            for c in deduped_candidates[:5]
            if question_rubric_service.get_rubric_if_cached(c["card"]) is not None
        ]

        if not filtered_candidates:
            logger.info("No rubric-ready candidates after prefilter")
            return []

        logger.info(
            "Multi-card evaluation: evaluating %s candidates (primary=%s)",
            len(filtered_candidates),
            primary_card_id,
        )

        recent_context = self._build_structured_context(
            db,
            session_id,
            theme_id,
            utterance_text,
            filtered_candidates,
        )

        judgments = self._batch_judge_answer_sufficiency(
            recent_context,
            filtered_candidates,
            session_id=session_id,
            model_override="gpt-5.4-mini",
            db=db,
        )

        updates = []
        for card_data, judgment in zip(filtered_candidates, judgments):
            card = card_data["card"]
            card_state = card_data["state"]
            conf = judgment.get("confidence", 0)

            if card_state.status == "pending":
                response_status = judgment.get("response_status")
                if conf < 0.35 or response_status in {
                    "question_only",
                    "not_started",
                    "not_yet",
                }:
                    continue

            update = self._update_card_state(
                db=db,
                card_state=card_state,
                card=card,
                utterance_id=utterance_id,
                utterance_text=utterance_text,
                judgment=judgment,
                model_used="gpt-5.4-mini",
            )
            if update:
                updates.append(update)
                if update["new_status"] in ("sufficient", "covered", "manually_checked"):
                    interview_service.clear_completed_card_routing(session, update["card_id"])

        db.commit()
        logger.info(f"Answer evaluated: {len(updates)} cards updated")
        return updates

    def _chinese_overlap_score(self, text: str, reference: str, n: int = 2) -> float:
        """Calculate character n-gram overlap between text and reference.

        Used for Chinese text matching since word-based splitting doesn't work well.

        Args:
            text: Text to check
            reference: Reference text to compare against
            n: N-gram size (default 2 for bigrams)

        Returns:
            Overlap score from 0.0 to 1.0
        """
        if not text or not reference:
            return 0.0
        text_ngrams = set(text[i : i + n] for i in range(len(text) - n + 1))
        ref_ngrams = set(reference[i : i + n] for i in range(len(reference) - n + 1))
        if not ref_ngrams:
            return 0.0
        return len(text_ngrams & ref_ngrams) / len(ref_ngrams)

    def _score_question_route(self, text_lower: str, card: QuestionCard) -> float:
        """Score how strongly a question-like utterance routes to a card.

        The spoken question should primarily match the card's actual question
        text. Coverage keywords and anchors are recall hints, but many are broad
        domain words such as "預約" or "當日"; they should not overtake a
        near-identical question.
        """
        score = 0.0

        question_text = (card.question_text or "").lower()
        if question_text:
            question_overlap = self._chinese_overlap_score(text_lower, question_text)
            if question_overlap > 0.1:
                score += 6.0 * question_overlap

            sequence_similarity = SequenceMatcher(None, text_lower, question_text).ratio()
            if sequence_similarity > 0.25:
                score += 4.0 * sequence_similarity

        focus_text = (card.focus_text or "").lower()
        if focus_text:
            focus_overlap = self._chinese_overlap_score(text_lower, focus_text)
            if focus_overlap > 0.1:
                score += 1.5 * focus_overlap

        coverage_rule = getattr(card, "coverage_rule", None) or {}
        keywords = (
            coverage_rule.get("expectedKeywords", [])
            or coverage_rule.get("expected_keywords", [])
            or []
        )
        keyword_score = 0.0
        for keyword in keywords:
            keyword_lower = str(keyword or "").lower().strip()
            if keyword_lower and keyword_lower in text_lower:
                keyword_score += 0.4
        score += min(keyword_score, 1.6)

        anchors = (
            coverage_rule.get("semanticAnchors", [])
            or coverage_rule.get("semantic_anchors", [])
            or []
        )
        anchor_score = 0.0
        for anchor in anchors:
            anchor_lower = str(anchor or "").lower().strip()
            if anchor_lower and anchor_lower in text_lower:
                anchor_score += 1.0
        score += min(anchor_score, 3.0)

        return score

    _STATE_PRIORITY_BONUS = {
        "listening": 5.0,
        "at_risk": 4.0,
        "probably_sufficient": 3.0,
        "pending": 0.0,
    }

    def _prefilter_candidates(
        self, utterance_text: str, candidate_cards: list, top_k: int = 5
    ) -> list:
        """Fast keyword-based prefilter to reduce candidates before LLM call.

        Scores each card by keyword overlap + state priority.
        Returns only cards with positive scores, up to top_k.
        """
        if len(candidate_cards) <= top_k:
            return candidate_cards

        text_lower = utterance_text.lower()
        scored = []
        for card_data in candidate_cards:
            card = card_data["card"]
            state = card_data.get("state")
            score = 0.0

            # State priority: already-active cards get significant boost
            if state:
                score += self._STATE_PRIORITY_BONUS.get(state.status, 0.0)

            # Check focus_text overlap using character bigrams (works better for Chinese)
            if card.focus_text:
                overlap = self._chinese_overlap_score(text_lower, card.focus_text.lower())
                if overlap > 0.15:
                    score += 2.0 * overlap

            # Check question_text overlap using character bigrams
            if card.question_text:
                overlap = self._chinese_overlap_score(text_lower, card.question_text.lower())
                if overlap > 0.1:
                    score += 1.0 * overlap

            # Check expectedKeywords from coverage_rule (substring matching works fine)
            coverage_rule = getattr(card, "coverage_rule", None) or {}
            keywords = coverage_rule.get("expectedKeywords", []) or []
            for kw in keywords:
                if kw and kw.lower() in text_lower:
                    score += 3.0

            # Check mustMentionElements (substring matching works fine)
            elements = coverage_rule.get("mustMentionElements", []) or []
            for elem in elements:
                elem_text = elem.get("text", "") if isinstance(elem, dict) else str(elem)
                if elem_text and elem_text.lower() in text_lower:
                    score += 2.0

            scored.append((score, card_data))

        # Sort by score descending; only keep cards with positive score
        scored.sort(key=lambda x: x[0], reverse=True)
        result = [item for score, item in scored if score > 0]

        return result[:top_k]

    def _load_candidate_cards(
        self,
        db: Session,
        session_id: str,
        theme_id: str,
        active_card_id: Optional[str] = None,
        statuses: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Load question cards that need evaluation for the current theme."""
        # Get all card states for cards in this theme that are not yet sufficient
        from app.models.interview_session import InterviewSession

        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()

        if not session:
            return []

        # Get question cards matching the active interview theme.
        cards = (
            db.query(QuestionCard)
            .filter(
                QuestionCard.document_id == session.document_id,
                QuestionCard.interview_theme_id == theme_id,
            )
            .all()
        )
        if active_card_id:
            cards = [card for card in cards if card.id == active_card_id]
        if not cards:
            return []

        # Get their states (exclude role-inapplicable cards)
        excluded_statuses = {"not_applicable_for_role", "needs_different_stakeholder"}
        card_states = (
            db.query(InterviewCardState)
            .filter(
                InterviewCardState.session_id == session_id,
                InterviewCardState.question_card_id.in_([card.id for card in cards]),
                InterviewCardState.status.in_(
                    statuses or ["pending", "listening", "probably_sufficient", "at_risk"]
                ),
                ~InterviewCardState.status.in_(excluded_statuses),
            )
            .all()
        )

        # Build candidate list
        state_by_card_id = {state.question_card_id: state for state in card_states}
        candidates = []

        for card in cards:
            if card.id in state_by_card_id:
                candidates.append({"card": card, "state": state_by_card_id[card.id]})

        return candidates

    def _build_structured_context(
        self,
        db: Session,
        session_id: str,
        theme_id: str,  # noqa: ARG002 – reserved for future theme filtering
        current_text: str,
        candidate_cards: List[Dict[str, Any]],  # noqa: ARG002 – reserved for enriched context
    ) -> str:
        """Build structured context for LLM evaluation.

        Includes recent utterances for the current theme so GPT can judge
        cumulative sufficiency (not just the latest sentence in isolation).
        Limited to last 10 utterances to avoid unbounded scans as interviews grow long.
        Capped at ~2000 chars to stay within reasonable prompt size.
        """
        # Fetch last 10 utterances ordered by sequence_index descending, then reverse for chronological
        recent_utterances = (
            db.query(LiveUtterance)
            .filter(
                LiveUtterance.session_id == session_id,
                LiveUtterance.theme_id == theme_id,
            )
            .order_by(LiveUtterance.sequence_index.desc())
            .limit(10)
            .all()
        )
        all_utterances = list(reversed(recent_utterances))

        lines = []
        for utt in all_utterances:
            lines.append(utt.transcript)

        # Add current utterance if not already included
        if current_text and (not all_utterances or all_utterances[-1].transcript != current_text):
            lines.append(current_text)

        # If total context exceeds ~2000 chars, keep the most recent lines
        context = "\n".join(lines)
        if len(context) > 2000:
            # Keep trimming oldest lines until under limit
            while lines and len("\n".join(lines)) > 2000:
                lines.pop(0)
            context = "\n".join(lines)

        return context

    def _batch_judge_answer_sufficiency(
        self,
        context: str,
        candidate_cards: List[Dict[str, Any]],
        session_id: str,  # noqa: ARG002 – kept for future per-session prompt tuning
        model_override: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """Batch judge all cards in a single GPT call.

        Phase 3: Supports model_override parameter. When doing provisional (live) evaluation,
        pass model_override="gpt-5.4-mini". Final evaluation uses gpt-5.4-mini (default).
        """
        import json

        from app.services.openai_service import openai_service

        # Phase 3: Use nano for provisional (live) evaluation, mini for final
        model = model_override or "gpt-5.4-mini"

        # Pre-load rubrics (cached only — no LLM calls, no fallback)
        rubrics = {}
        for card_data in candidate_cards:
            card = card_data["card"]
            rubric = question_rubric_service.get_rubric_if_cached(card)
            rubrics[card.id] = rubric or {"criteria": [], "answerTarget": card.question_text}

        cards_description = []
        for i, card_data in enumerate(candidate_cards):
            card = card_data["card"]

            rubric = rubrics[card.id]
            criteria = rubric.get("criteria", [])
            answer_target = rubric.get("answerTarget", card.question_text)

            # Build criteria description for prompt
            criteria_lines = []
            for criterion in criteria:
                crit_id = criterion.get("id", f"criterion_{len(criteria_lines)}")
                desc = criterion.get("description", "")
                crit_type = criterion.get("type", "value_slot")
                required = "必要" if criterion.get("required") else "選填"
                criteria_lines.append(f"  {crit_id}: {desc} (type={crit_type}, {required})")

            # Include current coverage progress
            state = card_data.get("state")
            current_status = state.status if state else "pending"
            existing_evidence = getattr(state, "evidence", None) or {} if state else {}
            already_satisfied = existing_evidence.get("satisfiedCriteria", []) or []

            cards_description.append(
                "\n".join(
                    [
                        f'{i}: question="{card.question_text}"',
                        f"focus=\"{card.focus_text or ''}\"",
                        f'answer_target="{answer_target}"',
                        (
                            f"criteria:\n" + "\n".join(criteria_lines)
                            if criteria_lines
                            else "criteria: (none)"
                        ),
                        f'current_status="{current_status}" already_satisfied={already_satisfied}',
                    ]
                )
            )

        cards_list = "\n".join(cards_description)

        # New criterion-based system prompt
        system_prompt = (
            "你是 BRD 訪談評估系統。你的任務是逐 criterion 判斷對話是否滿足每張卡片的評估標準。\n\n"
            "【重要】輸入來自即時語音辨識，可能有錯字、漏字、斷句不完整。請根據語意而非字面判斷。\n\n"
            "【最重要規則：區分「話題啟動」與「回答完成」】\n"
            "話題啟動 = 有人提到這張卡片的主題（提問、引導、或概述）。\n"
            "回答完成 = 語句內容提供了具體的情境、例子、行動、決策、數據或結果。\n"
            "話題啟動 ≠ 回答完成。提問只是啟動，不是完成。\n\n"
            "如果對話中最新的相關內容是提問形式（結尾是「嗎」「呢」「？」或含「哪些」「什麼」「如何」等疑問詞），"
            "即使提到了 criterion 的關鍵字：\n"
            "- relation 必須設為 topic_mention（不是 answer）\n"
            "- response_status 必須設為 question_only\n"
            "- 所有 criteria 必須設為 not_addressed\n"
            "- 不得給 partially_satisfied 或 satisfied\n\n"
            "只有以下情況才可標記 partially_satisfied 或 satisfied：\n"
            "- 語句描述了一個具體情境（「像是客戶要我...」「上次遇到...」）\n"
            "- 語句提供了一個具體例子或行動\n"
            "- 語句表達了明確的觀點或決策\n"
            "- 語句提供了數據或量化資訊\n\n"
            "判斷規則：\n"
            "1. 每張卡片有多個 criteria（評估項目），你必須逐項判斷。\n"
            "2. 只有實質回答（描述具體情況、表達明確觀點、提供資訊）才算滿足 criterion。\n"
            "3. 提問本身絕對不算滿足任何 criterion，即使提問中包含 criterion 的關鍵字。\n"
            "4. 每個 criterion 的 status 必須是以下之一：\n"
            "   - satisfied：已有明確、完整的回答內容，且有原文引述\n"
            "   - partially_satisfied：有提供部分資訊但不完整（必須是回答內容，不是提問）\n"
            "   - attempted_but_unresolved：語句嘗試回答但未能解決（如「不確定」「要再確認」）\n"
            "   - not_addressed：未提及，或僅在提問中提到關鍵字但尚無回答\n"
            "   - contradicted：前後矛盾或否定先前的回答\n"
            "   - not_applicable：該 criterion 不適用於此情境\n"
            "5. evidence_quotes 必須來自具有實質資訊的回答句，不能來自提問句。\n"
            "6. 沒有原文支持就不能標記 satisfied。\n\n"
            "每張卡片的 relation 欄位判斷：\n"
            "- answer：語句正在回答這個問題（必須有具體回答內容）\n"
            "- topic_mention：話題被提到但尚無實質回答（含提問、引導語）\n"
            "- tangential：提到了相關主題但不是直接回答\n"
            "- irrelevant：完全無關\n\n"
            "response_status 判斷：\n"
            "- responded：語句已給出實質回應（具體情境、例子、觀點、數據）\n"
            "- question_only：目前只有提問或引導語，尚無實質回答\n"
            "- clarification_question：語句是在反問以釐清問題\n"
            "- not_yet：尚未被討論\n\n"
            "resolution_status 判斷：\n"
            "- resolved：問題已被充分回答\n"
            "- partially_resolved：部分回答（必須有具體回答內容）\n"
            "- unresolved：提了但沒解決\n"
            "- not_started：完全未開始或僅有提問\n\n"
            "回傳格式必須是 JSON：\n"
            '{"evaluations": [{"relation": "topic_mention", "response_status": "question_only", '
            '"resolution_status": "not_started", '
            '"criteria": [{"criterion_id": "criterion_0", "status": "not_addressed", '
            '"normalized_value": null, "evidence_quotes": [], '
            '"evaluator_confidence": 0.95, "reason": "僅有提問，尚無回答"}], '
            '"suggested_followup": null}]}\n\n'
            "重要限制：\n"
            "- evaluations 陣列長度必須等於卡片數量，順序一一對應。\n"
            "- 禁止輸出 completion_score 或 is_sufficient（由程式計算）。\n"
            "- 一句話可以同時回答多張卡片，但每張 relation 為 answer 的卡片都必須有自己的具體 evidence_quotes。\n"
            "- 不得因為主題相近就替其他卡片累積完成度；只有完成條件被明確回答才可更新該卡。\n"
            "- 判斷時要看整段累計對話，不只看最新一句。\n"
            "- 如果對話中只有提問尚無回答，response_status 必須是 question_only，relation 必須是 topic_mention，"
            "所有 criteria 必須是 not_addressed。\n"
            "- suggested_followup 只在 response_status 為 responded 且回答不完整時才提供，否則設為 null。\n"
            "- suggested_followup 用繁體中文、口語化、可直接問出口。"
        )
        user_prompt = (
            f"到目前為止的對話內容：\n{context[:2000]}\n\n"
            f"提問重點卡片（共 {len(candidate_cards)} 張）：\n{cards_list}\n\n"
            f"請為每張卡片的每個 criterion 逐項判斷狀態，回傳 {len(candidate_cards)} 個評估結果。\n"
            f"suggested_followup 必須問「對話中還沒提到的部分」，不要重複對話中已經回答過的內容。\n"
            f"只輸出 JSON。"
        )

        try:
            result = openai_service.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                db=db,
                session_id=session_id,
                purpose="answer_evaluation",
            )
            logger.info(f"Batch judgment raw response: {str(result)[:300]}")

            # Phase 3: Parse result — try "evaluations" key FIRST, then fallback to other formats
            if isinstance(result, list):
                judgments_raw = result
            else:
                # Try "evaluations" first as per updated prompt
                for key in ["evaluations", "cards", "results", "judgments"]:
                    if key in result and isinstance(result[key], list):
                        judgments_raw = result[key]
                        break
                else:
                    # Handle dict with index keys like {"0": {...}, "1": {...}}
                    if all(k.isdigit() for k in result.keys()):
                        judgments_raw = [
                            result[str(i)] for i in range(len(candidate_cards)) if str(i) in result
                        ]
                    else:
                        judgments_raw = []

            judgments = []
            for i in range(len(candidate_cards)):
                if i < len(judgments_raw):
                    item = judgments_raw[i]
                    criterion_evals = item.get("criteria", []) or []

                    # Reuse pre-loaded rubric (no LLM call)
                    card = candidate_cards[i]["card"]
                    rubric = rubrics[card.id]
                    rubric_criteria = rubric.get("criteria", [])

                    # Use deterministic scorer
                    completion_score = answer_completion_scorer.calculate_completion(
                        rubric_criteria, criterion_evals
                    )
                    is_sufficient = answer_completion_scorer.is_sufficient(
                        rubric_criteria, criterion_evals, completion_score
                    )

                    evidence_quote = ""
                    for e in criterion_evals:
                        if e.get("evidence_quotes"):
                            evidence_quote = e["evidence_quotes"][0]
                            break

                    # Ensure card activation even when completion=0 but topic was touched
                    relation = item.get("relation", "irrelevant")
                    response_status = item.get("response_status", "not_yet")
                    effective_confidence = completion_score
                    if effective_confidence == 0 and relation in ("answer", "tangential"):
                        effective_confidence = 0.01  # activate card (listening)
                    if effective_confidence == 0 and response_status == "question_only":
                        effective_confidence = 0.01

                    judgments.append(
                        {
                            "confidence": effective_confidence,
                            "is_covered": is_sufficient,
                            "relation": relation,
                            "response_status": response_status,
                            "resolution_status": item.get("resolution_status", "not_started"),
                            "criterion_evaluations": criterion_evals,
                            "covered_element_ids": [
                                e["criterion_id"]
                                for e in criterion_evals
                                if e.get("status") == "satisfied"
                            ],
                            "missing_element_ids": [
                                e["criterion_id"]
                                for e in criterion_evals
                                if e.get("status")
                                in (
                                    "not_addressed",
                                    "attempted_but_unresolved",
                                    "partially_satisfied",
                                )
                            ],
                            "reason": "; ".join(
                                e.get("reason", "") for e in criterion_evals if e.get("reason")
                            ),
                            "suggested_followup": item.get("suggested_followup", "") or "",
                            "evidence_quote": evidence_quote,
                        }
                    )
                else:
                    judgments.append(
                        {
                            "confidence": 0.0,
                            "is_covered": False,
                            "relation": "irrelevant",
                            "response_status": "not_yet",
                            "criterion_evaluations": [],
                            "suggested_followup": "",
                            "evidence_quote": "",
                        }
                    )

            logger.info(
                f"Batch judgment for {len(candidate_cards)} cards: {[j['confidence'] for j in judgments]}"
            )
            return judgments

        except Exception as e:
            logger.error(f"Batch judgment failed: {e}", exc_info=True)
            # Fallback: return zeros
            return [{"confidence": 0.0, "is_covered": False}] * len(candidate_cards)

    def _update_card_state(
        self,
        db: Session,
        card_state: InterviewCardState,
        card: QuestionCard,
        utterance_id: str,
        utterance_text: str,
        judgment: Dict[str, Any],
        model_used: str = "gpt-5.4-mini",
    ) -> Optional[Dict[str, Any]]:
        """Update card state based on sufficiency judgment.

        Phase 3: Integrated with _reduce_state for deterministic state transitions.
        """
        old_status = card_state.status
        # Don't downgrade already completed cards
        if old_status in ("sufficient", "covered", "manually_checked"):
            return None

        ai_confidence = judgment.get("sufficiency_score", None) or judgment.get("confidence", 0.0)
        current_activation = float(card_state.activation_score or 0)
        current_completion = float(card_state.completion_score or 0)
        covered_element_ids = set(judgment.get("covered_element_ids", []) or [])
        missing_element_ids = set(judgment.get("missing_element_ids", []) or [])

        # Deterministic reducer with activation/completion separation
        new_status, new_activation, new_completion = reduce_card_state(
            current_status=old_status, judgment=judgment
        )
        # AI can suggest that a card is probably covered, but completion is a
        # product decision left to the facilitator. Terminal completion states
        # are only produced by explicit manual actions (see manual_complete_card).
        if new_status == "sufficient":
            new_status = "probably_sufficient"
            new_completion = min(new_completion, 0.85)
        # Scores only accumulate upward (never decrease)
        new_activation = max(current_activation, new_activation)
        new_completion = max(current_completion, new_completion)
        # Public confidence mirrors completion score for UI progress display.
        new_confidence = new_completion

        # Always write CardCoverageEvaluation for traceability (even if no state change)
        evaluation_seq = self._get_next_evaluation_seq(db, card_state.session_id, card.id)
        covered, missing = [], []
        if covered_element_ids or missing_element_ids:
            covered, missing = self._normalize_completion_element_ids(
                card=card,
                completion={
                    "covered_element_ids": list(covered_element_ids),
                    "missing_element_ids": list(missing_element_ids),
                },
            )

        coverage_eval = CardCoverageEvaluation(
            id=f"cce_{uuid.uuid4().hex[:12]}",
            session_id=card_state.session_id,
            card_id=card.id,
            state=new_status,
            confidence=new_confidence,
            covered_element_ids=covered or [],
            missing_element_ids=missing or [],
            evidence=(
                [{"evidence_quote": judgment.get("evidence_quote", "")}]
                if judgment.get("evidence_quote")
                else []
            ),
            evaluation_seq=evaluation_seq,
            model=model_used,
            prompt_version=None,
            created_at=datetime.utcnow(),
        )
        db.add(coverage_eval)

        # Write criterion-level evidence to append-only ledger
        # Skip for question-only turns — they activate cards but don't create progress
        response_status = judgment.get("response_status", "not_yet")
        criterion_evals = judgment.get("criterion_evaluations", [])
        _QUESTION_ONLY_STATUSES = frozenset(
            [
                "question_only",
                "not_yet",
                "not_started",
                "clarification_question",
            ]
        )
        is_question_only = response_status in _QUESTION_ONLY_STATUSES
        if criterion_evals and not is_question_only:
            persist_criterion_evidence(
                db=db,
                session_id=card_state.session_id,
                card_id=card.id,
                criterion_evaluations=criterion_evals,
                utterance_id=utterance_id,
                utterance_text=utterance_text,
                model=model_used,
                evaluation_seq=evaluation_seq,
            )

        # No meaningful progress — skip UI update but evaluation is still recorded
        if (
            new_status == old_status
            and new_activation <= current_activation
            and new_completion <= current_completion
        ):
            return None

        # Update card state
        card_state.status = new_status
        card_state.confidence = new_confidence
        card_state.activation_score = new_activation
        card_state.completion_score = new_completion
        existing_evidence = card_state.evidence_transcript or ""
        card_state.evidence_transcript = f"{existing_evidence}\n{utterance_text}".strip()
        judgment = preserve_existing_followup_when_empty(card_state.evidence, judgment)
        card_state.evidence = {
            "judgment": judgment,
            "utterance_id": utterance_id,
            "accumulated_confidence": new_confidence,
            "matchedTranscript": utterance_text,
            "coveredElementIds": covered,
            "missingElementIds": missing,
            "satisfiedCriteria": [
                e["criterion_id"]
                for e in judgment.get("criterion_evaluations", [])
                if e.get("status") == "satisfied"
            ],
            "criterionEvaluations": judgment.get("criterion_evaluations", []),
            "coveredAspectIds": covered,
            "timestamp": datetime.utcnow().isoformat(),
        }
        card_state.updated_at = datetime.utcnow()

        # Set answered_at when becoming sufficient
        if new_status in ["sufficient", "probably_sufficient"] and old_status not in [
            "sufficient",
            "probably_sufficient",
        ]:
            card_state.answered_at = datetime.utcnow()

        logger.info(
            f"Updated card state for question '{card.question_text[:30]}...': "
            f"{old_status} -> {new_status} (score: {ai_confidence:.2f}, seq: {evaluation_seq})"
        )

        return {
            "card_id": card.id,
            "card_state_id": card_state.id,
            "old_status": old_status,
            "new_status": new_status,
            "confidence": new_confidence,
            "activation_score": new_activation,
            "completion_score": new_completion,
            "evidence": card_state.evidence,
            "evidence_transcript": card_state.evidence_transcript,
            "judgment": judgment,
            "evaluation_seq": evaluation_seq,
        }


# Singleton instance
answer_evaluation_engine = AnswerEvaluationEngine()
