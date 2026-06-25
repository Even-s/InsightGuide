"""Answer Evaluation Engine - Core service for evaluating answer sufficiency."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.card_coverage_evaluation import CardCoverageEvaluation
from app.models.interview_session import InterviewCardState
from app.models.live_utterance import LiveUtterance
from app.models.question_card import QuestionCard
from app.services.answer_completion_scorer import answer_completion_scorer
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
        element IDs, with anchor IDs accepted as compatibility aliases.
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
        completion_percentage: float = 0,  # noqa: ARG002
        is_sufficient: bool = False,  # noqa: ARG002
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

    # High-confidence question detector: must have question signal AND lack answer signal
    _QUESTION_ENDINGS = ("?", "？", "呢", "嗎", "嘛")
    _QUESTION_MARKERS = (
        "哪些",
        "什麼",
        "如何",
        "為什麼",
        "有沒有",
        "是否",
        "能否",
        "怎麼",
        "請問",
        "想問",
        "可不可以",
        "你有",
        "你會",
    )
    _ANSWER_MARKERS = (
        "我們會",
        "我們用",
        "我們有",
        "我會",
        "我有",
        "我遇到",
        "之前有",
        "當時",
        "有一次",
        "例如",
        "像是",
        "客戶要",
        "客戶說",
        "主管會",
        "同事幫",
        "遇到過",
        "處理方式",
        "解決方案",
        "解決了",
        "後來就",
        "因為所以",
        "結果是",
        "通常會",
        "其實是",
        "我做的是",
        "我的做法",
        "我負責",
    )

    def _is_question_like(self, text: str) -> bool:
        """High-confidence question detector.

        Returns True only if the text has question markers AND lacks answer content markers.
        This avoids blocking real answers that happen to contain question words.
        """
        stripped = text.strip()
        if not stripped:
            return False

        has_question_signal = stripped.endswith(self._QUESTION_ENDINGS) or any(
            marker in stripped for marker in self._QUESTION_MARKERS
        )
        if not has_question_signal:
            return False

        has_answer_content = any(marker in stripped for marker in self._ANSWER_MARKERS)
        return not has_answer_content

    # Filler patterns that should skip LLM evaluation
    _FILLER_PATTERNS = frozenset(
        [
            "嗯",
            "嗯嗯",
            "好",
            "好的",
            "對",
            "對對",
            "是",
            "是的",
            "沒有",
            "沒",
            "嗯哼",
            "喔",
            "哦",
            "啊",
            "呃",
            "那個",
            "就是",
            "然後",
            "我想一下",
            "等一下",
            "讓我想想",
            "稍等",
            "ok",
            "okay",
            "yeah",
            "yes",
            "no",
            "hmm",
            "uh",
            "right",
            "sure",
            "got it",
            "i see",
            "mm",
        ]
    )

    def _should_skip_utterance(self, text: str) -> bool:
        """Return True if utterance is too trivial to warrant LLM evaluation."""
        stripped = text.strip()
        if len(stripped) < 5:
            return True
        normalized = stripped.lower().rstrip("。，.!?！？⋯…")
        if normalized in self._FILLER_PATTERNS:
            return True
        import re

        if re.fullmatch(r"[\s\W]+", stripped):
            return True
        return False

    def process_utterance(
        self,
        db: Session,
        session_id: str,
        utterance_id: str,
        utterance_text: str,
        section_id: str,
        speaker: str = "interviewee",
        asked_card_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process a new utterance. Routes questions to cards; evaluates answers for completion.
        """
        try:
            if self._should_skip_utterance(utterance_text):
                logger.info(
                    f"Skipping trivial utterance for session={session_id}: '{utterance_text[:30]}'"
                )
                return []

            logger.info(
                f"Processing utterance for session={session_id}, "
                f"section={section_id}, speaker={speaker}, text='{utterance_text[:50]}...'"
            )

            # Split: question → route to card; answer → evaluate completion
            if self._is_question_like(utterance_text):
                return self._route_question_to_card(
                    db, session_id, utterance_id, utterance_text, section_id, asked_card_id
                )
            else:
                return self._evaluate_answer(
                    db, session_id, utterance_id, utterance_text, section_id, speaker
                )

        except Exception as e:
            logger.error(f"Error processing utterance: {str(e)}", exc_info=True)
            db.rollback()
            return []

    def _route_question_to_card(
        self,
        db: Session,
        session_id: str,
        utterance_id: str,
        utterance_text: str,
        section_id: str,
        asked_card_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Route an interviewer question to the most relevant card. No completion scoring."""
        from app.models.interview_session import InterviewSession

        # Initialize answer buffer — subsequent answers will be buffered until user confirms
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if session and not asked_card_id:
            session.pending_answer_buffer = []

        # Find target card
        if asked_card_id:
            target_card_id = asked_card_id
            logger.info(f"Question routing: using frontend-provided askedCardId={asked_card_id}")
        else:
            target_card_id = self._find_best_matching_card(
                db, session_id, section_id, utterance_text
            )
            logger.info(f"Question routing: router found target={target_card_id}")

        if not target_card_id:
            logger.info("Question routing: no matching card found")
            return []

        # Load the card state
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
            return []

        # Don't re-route already completed cards
        if card_state.status in ("sufficient", "covered", "manually_checked"):
            return []

        card = db.query(QuestionCard).filter(QuestionCard.id == target_card_id).first()
        if not card:
            return []

        # Update session active_card_hint
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if session:
            session.active_card_hint_id = target_card_id

        # Activate card (pending → listening) with activation only, no completion
        old_status = card_state.status
        if old_status == "pending":
            card_state.status = "listening"
            card_state.activation_score = 1.0
            card_state.updated_at = datetime.utcnow()

            # Write audit record
            evaluation_seq = self._get_next_evaluation_seq(db, session_id, card.id)
            coverage_eval = CardCoverageEvaluation(
                id=f"cce_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                card_id=card.id,
                basis_type="live",
                transcript_revision_id=None,
                state="listening",
                confidence=0,
                covered_element_ids=[],
                missing_element_ids=[],
                evidence=[],
                evaluation_seq=evaluation_seq,
                model="router",
                prompt_version=None,
                created_at=datetime.utcnow(),
            )
            db.add(coverage_eval)
            db.commit()

            logger.info(f"Question routed: {target_card_id} pending → listening")

            return [
                {
                    "card_id": card.id,
                    "card_state_id": card_state.id,
                    "old_status": old_status,
                    "new_status": "listening",
                    "confidence": 0,
                    "activation_score": 1.0,
                    "completion_score": 0.0,
                    "evidence": None,
                    "evidence_transcript": None,
                    "judgment": {"response_status": "question_only", "suggested_followup": ""},
                    "evaluation_seq": evaluation_seq,
                }
            ]

        # Card already active — just update hint, no state change needed
        if session:
            db.commit()
        return []

    def _find_best_matching_card(
        self,
        db: Session,
        session_id: str,
        section_id: str,
        question_text: str,
    ) -> Optional[str]:
        """Find which card a question is about using text similarity. No state bonus."""
        candidates = self._load_candidate_cards(
            db,
            session_id,
            section_id,
            statuses=["pending", "listening", "probably_sufficient", "at_risk"],
        )
        if not candidates:
            return None

        text_lower = question_text.lower()
        best_score = 0.0
        best_card_id = None

        for card_data in candidates:
            card = card_data["card"]
            score = 0.0

            # Focus text overlap (highest signal for routing)
            if card.focus_text:
                overlap = self._chinese_overlap_score(text_lower, card.focus_text.lower())
                if overlap > 0.1:
                    score += 3.0 * overlap

            # Question text overlap
            if card.question_text:
                overlap = self._chinese_overlap_score(text_lower, card.question_text.lower())
                if overlap > 0.1:
                    score += 2.0 * overlap

            # Keywords
            coverage_rule = getattr(card, "coverage_rule", None) or {}
            keywords = (
                coverage_rule.get("expectedKeywords", [])
                or coverage_rule.get("expected_keywords", [])
                or []
            )
            for kw in keywords:
                if kw and kw.lower() in text_lower:
                    score += 3.0

            # Semantic anchors
            anchors = (
                coverage_rule.get("semanticAnchors", [])
                or coverage_rule.get("semantic_anchors", [])
                or []
            )
            for anchor in anchors:
                if anchor and anchor.lower() in text_lower:
                    score += 2.0

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
        section_id: str,
        question_text: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Public: find top-K candidate cards for a question. Returns scored list."""
        candidates = self._load_candidate_cards(
            db,
            session_id,
            section_id,
            statuses=["pending", "listening", "probably_sufficient", "at_risk"],
        )
        if not candidates:
            return []

        text_lower = question_text.lower()
        scored = []

        for card_data in candidates:
            card = card_data["card"]
            score = 0.0

            if card.focus_text:
                overlap = self._chinese_overlap_score(text_lower, card.focus_text.lower())
                if overlap > 0.1:
                    score += 3.0 * overlap

            if card.question_text:
                overlap = self._chinese_overlap_score(text_lower, card.question_text.lower())
                if overlap > 0.1:
                    score += 2.0 * overlap

            coverage_rule = getattr(card, "coverage_rule", None) or {}
            keywords = (
                coverage_rule.get("expectedKeywords", [])
                or coverage_rule.get("expected_keywords", [])
                or []
            )
            for kw in keywords:
                if kw and kw.lower() in text_lower:
                    score += 3.0

            anchors = (
                coverage_rule.get("semanticAnchors", [])
                or coverage_rule.get("semantic_anchors", [])
                or []
            )
            for anchor in anchors:
                if anchor and anchor.lower() in text_lower:
                    score += 2.0

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
        section_id: str,
        speaker: str = "interviewee",
    ) -> List[Dict[str, Any]]:
        """Evaluate an answer for completion.

        When active_card_id is user-confirmed, evaluation is EXCLUSIVE to that card.
        Other cards cannot accumulate completion from answer utterances.
        """
        from app.models.interview_session import InterviewSession

        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        active_card_id = session.active_card_id if session else None
        active_source = session.active_card_source if session else None
        active_hint_id = active_card_id or (session.active_card_hint_id if session else None)

        # If no active card and pending_answer_buffer exists, buffer this utterance
        if not active_hint_id and session and session.pending_answer_buffer is not None:
            buffer = session.pending_answer_buffer or []
            buffer.append(utterance_id)
            session.pending_answer_buffer = buffer
            db.commit()
            logger.info(
                f"Buffered utterance {utterance_id} (waiting for card confirmation, buffer={len(buffer)})"
            )
            return []

        # EXCLUSIVE MODE: when active_card_id is user-confirmed, only evaluate that card
        is_exclusive = active_card_id and active_source in ("user_confirmed", "manual_selected")

        if is_exclusive:
            # Only load and evaluate the active card
            candidate_cards = self._load_candidate_cards(
                db,
                session_id,
                section_id,
                active_card_id=active_card_id,
                statuses=["listening", "probably_sufficient", "at_risk"],
            )
            if not candidate_cards:
                logger.info(f"Active card {active_card_id} not in evaluable state; skipping")
                return []

            filtered_candidates = [
                c
                for c in candidate_cards
                if question_rubric_service.get_rubric_if_cached(c["card"]) is not None
            ]
            if not filtered_candidates:
                return []

            logger.info(f"Exclusive mode: evaluating only active card {active_card_id}")
        else:
            # NON-EXCLUSIVE: evaluate all candidates (legacy/no-active-card mode)
            candidate_cards = self._load_candidate_cards(
                db,
                session_id,
                section_id,
                statuses=["pending", "listening", "probably_sufficient", "at_risk"],
            )
            if not candidate_cards:
                logger.info("No candidate cards found for answer; skipping")
                return []

            filtered_candidates = self._prefilter_candidates(utterance_text, candidate_cards)
            filtered_candidates = [
                c
                for c in filtered_candidates
                if question_rubric_service.get_rubric_if_cached(c["card"]) is not None
            ]

            if active_hint_id and not any(
                c["card"].id == active_hint_id for c in filtered_candidates
            ):
                hint_card = next(
                    (c for c in candidate_cards if c["card"].id == active_hint_id), None
                )
                if hint_card and question_rubric_service.get_rubric_if_cached(hint_card["card"]):
                    filtered_candidates.insert(0, hint_card)

            if not filtered_candidates:
                logger.info("No rubric-ready candidates after prefilter")
                return []

            logger.info(f"Non-exclusive mode: evaluating {len(filtered_candidates)} candidates")

        recent_context = self._build_structured_context(
            db,
            session_id,
            section_id,
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

        # In exclusive mode, no pending-card gating needed (only active card is evaluated)
        # In non-exclusive mode, one answer turn can advance at most one pending card
        has_advanced_pending = False
        max_confidence = (
            max((j.get("confidence", 0) for j in judgments), default=0) if not is_exclusive else 0
        )

        updates = []
        for card_data, judgment in zip(filtered_candidates, judgments):
            card = card_data["card"]
            card_state = card_data["state"]
            conf = judgment.get("confidence", 0)

            if not is_exclusive and conf > 0 and card_state.status == "pending":
                if conf < max_confidence:
                    continue
                if has_advanced_pending:
                    continue
                has_advanced_pending = True

            update = self._update_card_state(
                db=db,
                card_state=card_state,
                card=card,
                utterance_id=utterance_id,
                utterance_text=utterance_text,
                judgment=judgment,
                is_partial=False,
                model_used="gpt-5.4-mini",
            )
            if update:
                updates.append(update)

        db.commit()
        logger.info(f"Answer evaluated: {len(updates)} cards updated")
        return updates

    def process_partial_transcript(
        self,
        db: Session,
        session_id: str,
        transcript_text: str,
        section_id: str,
        speaker: str = "interviewee",  # noqa: ARG002
        active_card_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process an in-flight transcript buffer without creating an utterance row.

        This lets interview mode start card matching while Realtime transcription
        is still streaming deltas. The completed transcript is still saved later
        through create_utterance().
        """
        transcript_text = transcript_text.strip()
        if len(transcript_text) < 8:
            return []

        try:
            logger.info(
                "Processing partial transcript for session=%s, section=%s, text='%s...'",
                session_id,
                section_id,
                transcript_text[:30],
            )

            # Use a temporary ID for partial transcripts
            temp_utterance_id = f"partial_{datetime.utcnow().timestamp()}"

            candidate_cards = self._load_candidate_cards(
                db,
                session_id,
                section_id,
                active_card_id=active_card_id,
                statuses=["listening"],
            )
            if not candidate_cards:
                logger.info("No active card found for partial transcript")
                return []

            judgments = self._batch_judge_answer_sufficiency(
                transcript_text, candidate_cards, session_id=session_id, db=db
            )

            # Phase 2: Cap partial transcript judgments at probably_sufficient
            # Partial transcripts cannot produce "sufficient" state
            for judgment in judgments:
                if judgment.get("is_covered") or judgment.get("is_sufficient"):
                    judgment["is_covered"] = False
                    judgment["is_sufficient"] = False
                    # Cap confidence to prevent sufficient state
                    if judgment.get("confidence", 0) >= 0.85:
                        judgment["confidence"] = 0.80

            updates = []
            for card_data, judgment in zip(candidate_cards, judgments):
                update = self._update_card_state(
                    db=db,
                    card_state=card_data["state"],
                    card=card_data["card"],
                    utterance_id=temp_utterance_id,
                    utterance_text=transcript_text,
                    judgment=judgment,
                    is_partial=True,
                    model_used="gpt-5.4-mini",
                )
                if update:
                    updates.append(update)

            db.commit()
            logger.info(
                "Processed partial transcript for active card: %s/%s cards updated",
                len(updates),
                len(candidate_cards),
            )
            return updates

        except Exception as e:
            logger.error(f"Error processing partial transcript: {str(e)}", exc_info=True)
            db.rollback()
            return []

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
        section_id: str,
        active_card_id: Optional[str] = None,
        statuses: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Load question cards that need evaluation for the current section."""
        # Get all card states for cards in this section that are not yet sufficient
        from app.models.interview_session import InterviewSession

        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()

        if not session:
            return []

        from sqlalchemy import or_

        # Get question cards matching by theme_id or section_id
        cards = (
            db.query(QuestionCard)
            .filter(
                QuestionCard.document_id == session.document_id,
                or_(
                    QuestionCard.interview_theme_id == section_id,
                    QuestionCard.section_id == section_id,
                ),
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
        section_id: str,  # noqa: ARG002 – reserved for future theme filtering
        current_text: str,
        candidate_cards: List[Dict[str, Any]],  # noqa: ARG002 – reserved for enriched context
    ) -> str:
        """Build structured context for LLM evaluation.

        Includes ALL utterances for the current theme/section so GPT can judge
        cumulative sufficiency (not just the latest sentence in isolation).
        Capped at ~2000 chars to stay within reasonable prompt size.

        Note: LiveUtterance model does not have theme_id or section_id fields,
        so we currently fetch all utterances for the session. Future enhancement
        could add theme_id filtering if the model is updated.
        """
        all_utterances = (
            db.query(LiveUtterance)
            .filter(
                LiveUtterance.session_id == session_id,
            )
            .order_by(LiveUtterance.created_at.asc())
            .all()
        )

        lines = []
        for utt in all_utterances:
            speaker = utt.speaker or "speaker"
            lines.append(f"[{speaker}]: {utt.transcript}")

        # Add current utterance if not already included
        if current_text and (not all_utterances or all_utterances[-1].transcript != current_text):
            lines.append(f"[current]: {current_text}")

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
            "回答完成 = 受訪者提供了具體的情境、例子、行動、決策、數據或結果。\n"
            "話題啟動 ≠ 回答完成。提問只是啟動，不是完成。\n\n"
            "如果對話中最新的相關內容是提問形式（結尾是「嗎」「呢」「？」或含「哪些」「什麼」「如何」等疑問詞），"
            "即使提到了 criterion 的關鍵字：\n"
            "- relation 必須設為 topic_mention（不是 answer）\n"
            "- response_status 必須設為 question_only\n"
            "- 所有 criteria 必須設為 not_addressed\n"
            "- 不得給 partially_satisfied 或 satisfied\n\n"
            "只有以下情況才可標記 partially_satisfied 或 satisfied：\n"
            "- 受訪者描述了一個具體情境（「像是客戶要我...」「上次遇到...」）\n"
            "- 受訪者提供了一個具體例子或行動\n"
            "- 受訪者表達了明確的觀點或決策\n"
            "- 受訪者提供了數據或量化資訊\n\n"
            "判斷規則：\n"
            "1. 每張卡片有多個 criteria（評估項目），你必須逐項判斷。\n"
            "2. 只有實質回答（描述具體情況、表達明確觀點、提供資訊）才算滿足 criterion。\n"
            "3. 提問本身絕對不算滿足任何 criterion，即使提問中包含 criterion 的關鍵字。\n"
            "4. 每個 criterion 的 status 必須是以下之一：\n"
            "   - satisfied：受訪者已給出明確、完整的回答，且有原文引述\n"
            "   - partially_satisfied：受訪者有提供部分資訊但不完整（必須是回答內容，不是提問）\n"
            "   - attempted_but_unresolved：受訪者嘗試回答但未能解決（如「不確定」「要再確認」）\n"
            "   - not_addressed：未提及，或僅在提問中提到關鍵字但尚無回答\n"
            "   - contradicted：前後矛盾或否定先前的回答\n"
            "   - not_applicable：該 criterion 不適用於此情境\n"
            "5. evidence_quotes 必須來自受訪者的回答句，不能來自提問句。\n"
            "6. 沒有原文支持就不能標記 satisfied。\n\n"
            "每張卡片的 relation 欄位判斷：\n"
            "- answer：受訪者正在回答這個問題（必須有具體回答內容）\n"
            "- topic_mention：話題被提到但尚無實質回答（含提問、引導語）\n"
            "- tangential：提到了相關主題但不是直接回答\n"
            "- irrelevant：完全無關\n\n"
            "response_status 判斷：\n"
            "- responded：受訪者已給出實質回應（具體情境、例子、觀點、數據）\n"
            "- question_only：目前只有提問或引導語，尚無實質回答\n"
            "- clarification_question：受訪者反問以釐清問題\n"
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
            "- 每句話通常只對應 0 或 1 張卡片。relation 為 answer 的卡片不應超過 1 張。\n"
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
            # Phase 3: Use model parameter from argument (nano for live, mini for final)
            response = openai_service.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            result = json.loads(content)
            logger.info(f"Batch judgment raw response: {content[:300]}")

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
        is_partial: bool = False,
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
        is_covered = judgment.get("is_sufficient", None) or judgment.get("is_covered", False)
        current_activation = float(card_state.activation_score or 0)
        current_completion = float(card_state.completion_score or 0)
        covered_element_ids = set(judgment.get("covered_element_ids", []) or [])
        missing_element_ids = set(judgment.get("missing_element_ids", []) or [])
        if covered_element_ids or missing_element_ids:
            covered, missing = self._normalize_completion_element_ids(
                card=card,
                completion={
                    "covered_element_ids": list(covered_element_ids),
                    "missing_element_ids": list(missing_element_ids),
                },
                completion_percentage=ai_confidence * 100,
                is_sufficient=bool(is_covered),
            )
        else:
            covered, missing = [], []

        # Deterministic reducer with activation/completion separation
        new_status, new_activation, new_completion = self._reduce_state(
            current_status=old_status, judgment=judgment, is_partial=is_partial
        )
        # Scores only accumulate upward (never decrease)
        new_activation = max(current_activation, new_activation)
        new_completion = max(current_completion, new_completion)
        # confidence field = completion_score for backward compatibility
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
                completion_percentage=ai_confidence * 100,
                is_sufficient=bool(is_covered),
            )

        coverage_eval = CardCoverageEvaluation(
            id=f"cce_{uuid.uuid4().hex[:12]}",
            session_id=card_state.session_id,
            card_id=card.id,
            basis_type="live",
            transcript_revision_id=None,
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
        is_question_only = response_status in self._QUESTION_ONLY_STATUSES
        if criterion_evals and not is_question_only:
            self._persist_criterion_evidence(
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
        judgment = self._preserve_existing_followup_when_empty(card_state.evidence, judgment)
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

    _QUESTION_ONLY_STATUSES = frozenset(
        [
            "question_only",
            "not_yet",
            "not_started",
            "clarification_question",
        ]
    )

    def _reduce_state(
        self, current_status: str, judgment: dict, is_partial: bool = False
    ) -> tuple[str, float, float]:
        """Deterministic state reducer using activation/completion separation.

        Returns (new_status, activation_score, completion_score).

        activation_score: Is this card's topic being discussed? (0 or 1)
        completion_score: How much of the criteria are answered? (0.0–1.0)

        State mapping:
        - activation=0, completion=0 → pending
        - activation>0, completion=0 → listening (card glows, progress=0%)
        - activation>0, completion>0 → probably_sufficient (progress bar)
        - all gates met → sufficient
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
        if response_status in self._QUESTION_ONLY_STATUSES:
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

        # Constraints
        if is_partial and target == "sufficient":
            target = "probably_sufficient"
            completion_score = min(completion_score, 0.80)

        if not has_evidence and target == "sufficient":
            target = "probably_sufficient"

        # State can only move forward
        STATE_ORDER = {"pending": 0, "listening": 1, "probably_sufficient": 2, "sufficient": 3}
        current_order = STATE_ORDER.get(current_status, 0)
        target_order = STATE_ORDER.get(target, 0)

        if target_order < current_order:
            target = current_status

        return target, activation_score, completion_score

    def _preserve_existing_followup_when_empty(
        self,
        existing_evidence: Optional[Dict[str, Any]],
        judgment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Keep the last useful follow-up when a later judgment returns an empty one."""
        next_followup = (
            judgment.get("suggested_followup") or judgment.get("suggestedFollowup") or ""
        )
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

    def _persist_criterion_evidence(
        self,
        db: Session,
        session_id: str,
        card_id: str,
        criterion_evaluations: List[Dict[str, Any]],
        utterance_id: str,
        utterance_text: str,
        model: str,
        evaluation_seq: int,
    ) -> None:
        """Write criterion-level evidence to the append-only ledger."""
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
                utterance_id=utterance_id if not utterance_id.startswith("partial_") else None,
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

    def _load_existing_evidence(
        self,
        db: Session,
        session_id: str,
        card_id: str,
    ) -> Dict[str, str]:
        """Load best evidence status per criterion from ledger. Returns {criterion_id: best_status}."""
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

    def _derive_state_from_ledger(
        self,
        db: Session,
        session_id: str,
        card_id: str,
        rubric_criteria: List[Dict[str, Any]],
        is_partial: bool = False,
    ) -> tuple:
        """Derive card state from evidence ledger using deterministic scorer.

        Returns (state, completion_score).
        """
        evidence_statuses = self._load_existing_evidence(db, session_id, card_id)
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
            completion_score, is_sufficient, has_response, is_partial
        )
        return (state, completion_score)

    def run_final_coverage(
        self,
        db: Session,
        session_id: str,
        transcript_revision_id: str,
    ) -> List[Dict[str, Any]]:
        """Run final card coverage evaluation after diarization completes.

        Phase 2: This method is called after final_utterances are written.
        It evaluates all cards against the complete diarized transcript and writes
        CardCoverageEvaluation records with basis_type='final'.

        Args:
            db: Database session
            session_id: Interview session ID
            transcript_revision_id: TranscriptRevision ID for the final transcript

        Returns:
            List of final coverage evaluation results
        """
        from app.models.final_utterance import FinalUtterance
        from app.models.interview_session import InterviewSession
        from app.models.interview_theme import InterviewTheme
        from app.models.question_card import QuestionCard

        logger.info(f"Running final coverage evaluation for session {session_id}")

        # Load session
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            logger.error(f"Session {session_id} not found")
            return []

        # Load all final utterances for this revision
        final_utterances = (
            db.query(FinalUtterance)
            .filter(
                FinalUtterance.session_id == session_id,
                FinalUtterance.transcript_revision_id == transcript_revision_id,
            )
            .order_by(FinalUtterance.sequence_index)
            .all()
        )

        if not final_utterances:
            logger.warning(f"No final utterances found for session {session_id}")
            return []

        # Load all question cards for this document
        themes = (
            db.query(InterviewTheme)
            .filter(
                InterviewTheme.document_id == session.document_id,
                InterviewTheme.is_enabled == True,
            )
            .order_by(InterviewTheme.order_index)
            .all()
        )

        all_cards = []
        for theme in themes:
            cards = (
                db.query(QuestionCard)
                .filter(
                    QuestionCard.interview_theme_id == theme.id,
                )
                .order_by(QuestionCard.order_index)
                .all()
            )
            for card in cards:
                all_cards.append(
                    {
                        "card": card,
                        "theme_id": theme.id,
                        "theme_title": theme.title,
                    }
                )

        if not all_cards:
            logger.warning(f"No question cards found for session {session_id}")
            return []

        # Group utterances by theme (for now, use all utterances as context)
        # TODO: Phase 3 will use theme-based grouping
        full_transcript = " ".join([u.transcript for u in final_utterances])

        logger.info(
            f"Final coverage: evaluating {len(all_cards)} cards against "
            f"{len(final_utterances)} utterances ({len(full_transcript)} chars)"
        )

        # Run batch judgment with all cards
        judgments = self._batch_judge_answer_sufficiency(
            full_transcript, all_cards, session_id=session_id, db=db
        )

        # Write CardCoverageEvaluation records with basis_type='final'
        results = []
        for card_data, judgment in zip(all_cards, judgments):
            card = card_data["card"]

            # Determine state based on judgment
            ai_confidence = judgment.get("sufficiency_score", None) or judgment.get(
                "confidence", 0.0
            )
            is_covered = judgment.get("is_sufficient", None) or judgment.get("is_covered", False)
            covered_element_ids = judgment.get("covered_element_ids", []) or []
            missing_element_ids = judgment.get("missing_element_ids", []) or []

            if covered_element_ids or missing_element_ids:
                covered, missing = self._normalize_completion_element_ids(
                    card=card,
                    completion={
                        "covered_element_ids": list(covered_element_ids),
                        "missing_element_ids": list(missing_element_ids),
                    },
                    completion_percentage=ai_confidence * 100,
                    is_sufficient=bool(is_covered),
                )
            else:
                covered, missing = [], []

            # Determine state using the same _reduce_state() method for consistency
            state, _ = self._reduce_state(
                current_status="pending",
                judgment={
                    "confidence": ai_confidence,
                    "is_covered": is_covered,
                    "evidence_quote": judgment.get("evidence_quote", ""),
                    "missing_element_ids": missing,
                    "covered_element_ids": covered,
                },
                is_partial=False,
            )

            # Get next evaluation_seq
            evaluation_seq = self._get_next_evaluation_seq(db, session_id, card.id)

            # Create CardCoverageEvaluation with basis_type='final'
            coverage_eval = CardCoverageEvaluation(
                id=f"cce_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                card_id=card.id,
                basis_type="final",
                transcript_revision_id=transcript_revision_id,
                state=state,
                confidence=ai_confidence,
                covered_element_ids=covered or [],
                missing_element_ids=missing or [],
                evidence=[],  # TODO: Phase 3 will populate structured evidence with quotes
                evaluation_seq=evaluation_seq,
                model="gpt-5.4-mini",
                prompt_version=None,
                created_at=datetime.utcnow(),
            )
            db.add(coverage_eval)

            results.append(
                {
                    "card_id": card.id,
                    "state": state,
                    "confidence": ai_confidence,
                    "covered_element_ids": covered,
                    "missing_element_ids": missing,
                    "evaluation_seq": evaluation_seq,
                }
            )

        db.commit()
        logger.info(f"Final coverage complete: wrote {len(results)} evaluations")

        return results


# Singleton instance
answer_evaluation_engine = AnswerEvaluationEngine()
