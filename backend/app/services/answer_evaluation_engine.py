"""Answer Evaluation Engine - Core service for evaluating answer sufficiency."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.embedding_service import embedding_service
from app.services.scoring_service import scoring_service
from app.services.semantic_judge_service import semantic_judge_service
from app.services.question_card_service import question_card_service
from app.models.question_card import QuestionCard
from app.models.interview_session import InterviewCardState
from app.models.utterance import Utterance

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
        self.embedding_service = embedding_service
        self.scoring_service = scoring_service
        self.semantic_judge = semantic_judge_service

    def _get_required_element_ids(self, card: QuestionCard) -> List[str]:
        """Return canonical element IDs that drive answer sufficiency.

        mustMentionElements are the visible "important elements" in interview mode.
        semanticAnchors are matching hints that normalize into at most three
        element IDs, with anchor IDs accepted as compatibility aliases.
        """
        coverage_rule = question_card_service.normalize_coverage_rule_for_important_elements(
            getattr(card, 'coverage_rule', None) or {}
        )
        semantic_anchors = coverage_rule.get('semanticAnchors', []) or []
        must_mention_elements = coverage_rule.get('mustMentionElements', []) or []

        element_ids = [
            f"element_{index}"
            for index, element in enumerate(must_mention_elements)
            if element
        ]
        if element_ids:
            return element_ids

        return [
            f"anchor_{index}"
            for index, anchor in enumerate(semantic_anchors)
            if anchor
        ]

    def _canonicalize_element_ids(self, card: QuestionCard, element_ids: set[str]) -> set[str]:
        """Map AI-returned anchor IDs into the canonical completion ID space."""
        coverage_rule = question_card_service.normalize_coverage_rule_for_important_elements(
            getattr(card, 'coverage_rule', None) or {}
        )
        must_mention_elements = coverage_rule.get('mustMentionElements', []) or []
        element_count = len([element for element in must_mention_elements if element])
        required_element_ids = set(self._get_required_element_ids(card))
        if not required_element_ids:
            return set(element_ids)

        canonical_ids: set[str] = set()
        for element_id in element_ids:
            if element_id in required_element_ids:
                canonical_ids.add(element_id)
                continue

            if element_count and element_id.startswith('anchor_'):
                try:
                    index = int(element_id.split('_', 1)[1])
                except (IndexError, ValueError):
                    continue
                mapped_id = f"element_{index % element_count}"
                if mapped_id in required_element_ids:
                    canonical_ids.add(mapped_id)

        return canonical_ids

    def _calculate_element_progress(
        self,
        card: QuestionCard,
        covered_element_ids: set[str]
    ) -> Optional[float]:
        """Calculate answer progress from covered answer elements."""
        required_element_ids = set(self._get_required_element_ids(card))
        if not required_element_ids:
            return None

        covered_required_ids = required_element_ids.intersection(covered_element_ids)
        return len(covered_required_ids) / len(required_element_ids)

    def _normalize_completion_element_ids(
        self,
        card: QuestionCard,
        completion: Dict[str, Any],
        completion_percentage: float,
        is_sufficient: bool
    ) -> tuple[List[str], List[str]]:
        """Keep AI completion percentage and element IDs internally consistent."""
        required_element_ids = set(self._get_required_element_ids(card))
        covered_element_ids = self._canonicalize_element_ids(
            card,
            set(completion.get('covered_element_ids', []) or [])
        )
        missing_element_ids = self._canonicalize_element_ids(
            card,
            set(completion.get('missing_element_ids', []) or [])
        )

        if not required_element_ids:
            return sorted(covered_element_ids), sorted(missing_element_ids - covered_element_ids)

        covered_element_ids &= required_element_ids
        missing_element_ids &= required_element_ids

        if is_sufficient and completion_percentage >= 85:
            covered_element_ids = set(required_element_ids)
            missing_element_ids = set()
        elif completion_percentage >= 90 and not missing_element_ids:
            covered_element_ids = set(required_element_ids)
            missing_element_ids = set()
        elif missing_element_ids:
            covered_element_ids = required_element_ids - missing_element_ids

        return sorted(covered_element_ids), sorted(missing_element_ids - covered_element_ids)

    def process_utterance(
        self,
        db: Session,
        session_id: str,
        utterance_id: str,
        utterance_text: str,
        section_id: str,
        speaker: str = "interviewee"
    ) -> List[Dict[str, Any]]:
        """
        Process a new utterance and update card states.

        Main entry point for answer evaluation processing.

        Args:
            db: Database session
            session_id: Interview session ID
            utterance_id: Utterance ID
            utterance_text: Transcribed text
            section_id: Current section ID
            speaker: Speaker identifier (interviewer or interviewee)

        Returns:
            List of card state updates (for event emission)

        Example:
            >>> updates = engine.process_utterance(
            ...     db, session_id, utt_id, "系統需要支援多語言", section_id, "interviewee"
            ... )
            >>> for update in updates:
            ...     print(f"Card {update['card_id']}: {update['new_status']}")
        """
        try:
            logger.info(
                f"Processing utterance for session={session_id}, "
                f"section={section_id}, speaker={speaker}, text='{utterance_text[:50]}...'"
            )

            # Only evaluate interviewee responses
            if speaker != "interviewee":
                logger.info("Skipping interviewer utterance")
                return []

            # Stage 1: Load candidate cards
            candidate_cards = self._load_candidate_cards(db, session_id, section_id)

            if not candidate_cards:
                logger.info("No candidate cards found")
                return []

            logger.info(f"Found {len(candidate_cards)} candidate cards")

            # Get recent context for better evaluation
            recent_context = self._get_recent_context(db, session_id, section_id, utterance_text)
            logger.info(f"Using context window: {len(recent_context)} chars")

            # Stage 2: AI sufficiency scoring for each active card on this section.
            # This uses accumulated transcript context so the card progress reflects
            # everything the interviewee has said so far.
            updates = []
            for card_data in candidate_cards:
                card = card_data['card']
                card_state = card_data['state']

                judgment = self._judge_answer_sufficiency(
                    recent_context,
                    card,
                    session_id=session_id,
                )

                # Update card state if score is high enough
                update = self._update_card_state(
                    db=db,
                    card_state=card_state,
                    card=card,
                    utterance_id=utterance_id,
                    utterance_text=utterance_text,
                    judgment=judgment
                )

                if update:
                    updates.append(update)

            db.commit()

            logger.info(
                "Processed utterance with AI sufficiency scoring: %s/%s cards updated",
                len(updates),
                len(candidate_cards),
            )

            return updates

        except Exception as e:
            logger.error(f"Error processing utterance: {str(e)}", exc_info=True)
            db.rollback()
            return []

    def process_partial_transcript(
        self,
        db: Session,
        session_id: str,
        transcript_text: str,
        section_id: str,
        speaker: str = "interviewee"
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

        # Only evaluate interviewee responses
        if speaker != "interviewee":
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

            return self.process_utterance(
                db=db,
                session_id=session_id,
                utterance_id=temp_utterance_id,
                utterance_text=transcript_text,
                section_id=section_id,
                speaker=speaker
            )

        except Exception as e:
            logger.error(f"Error processing partial transcript: {str(e)}", exc_info=True)
            return []

    def _load_candidate_cards(
        self,
        db: Session,
        session_id: str,
        section_id: str
    ) -> List[Dict[str, Any]]:
        """Load question cards that need evaluation for the current section."""
        # Get all card states for cards in this section that are not yet sufficient
        from app.models.interview_session import InterviewSession

        session = db.query(InterviewSession).filter(
            InterviewSession.id == session_id
        ).first()

        if not session:
            return []

        # Get all question cards for this section
        cards = db.query(QuestionCard).filter(
            QuestionCard.document_id == session.document_id,
            QuestionCard.section_id == section_id
        ).all()

        # Get their states
        card_states = db.query(InterviewCardState).filter(
            InterviewCardState.session_id == session_id,
            InterviewCardState.question_card_id.in_([card.id for card in cards]),
            InterviewCardState.status.in_(['pending', 'listening', 'probably_sufficient', 'at_risk'])
        ).all()

        # Build candidate list
        state_by_card_id = {state.question_card_id: state for state in card_states}
        candidates = []

        for card in cards:
            if card.id in state_by_card_id:
                candidates.append({
                    'card': card,
                    'state': state_by_card_id[card.id]
                })

        return candidates

    def _get_recent_context(
        self,
        db: Session,
        session_id: str,
        section_id: str,
        current_text: str,
        max_chars: int = 2000
    ) -> str:
        """Get recent conversation context for better evaluation."""
        # Get recent interviewee utterances from this section
        recent_utterances = db.query(Utterance).filter(
            Utterance.session_id == session_id,
            Utterance.section_id == section_id,
            Utterance.speaker == "interviewee"
        ).order_by(
            Utterance.created_at.desc()
        ).limit(10).all()

        # Build context from recent to old
        context_parts = [current_text]
        current_length = len(current_text)

        for utterance in reversed(recent_utterances):
            text = utterance.transcript.strip()
            if text and text != current_text:
                if current_length + len(text) + 1 > max_chars:
                    break
                context_parts.insert(0, text)
                current_length += len(text) + 1

        return " ".join(context_parts)

    def _judge_answer_sufficiency(
        self,
        context: str,
        card: QuestionCard,
        session_id: str
    ) -> Dict[str, Any]:
        """Use AI to judge if the answer is sufficient for BRD writing."""
        coverage_rule = question_card_service.normalize_coverage_rule_for_important_elements(
            getattr(card, 'coverage_rule', None) or {}
        )

        topic_card = {
            "title": card.question_text,
            "description": card.question_type,
            "coverageRule": coverage_rule
        }

        judgment = self.semantic_judge.judge_coverage(
            utterance_text=context,
            topic_card=topic_card,
            session_id=session_id
        )

        return judgment

    def _update_card_state(
        self,
        db: Session,
        card_state: InterviewCardState,
        card: QuestionCard,
        utterance_id: str,
        utterance_text: str,
        judgment: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update card state based on sufficiency judgment."""
        old_status = card_state.status
        sufficiency_score = judgment.get('sufficiency_score', 0.0)
        is_sufficient = judgment.get('is_sufficient', False)

        # Determine new status
        new_status = old_status
        if is_sufficient:
            new_status = "sufficient"
        elif sufficiency_score >= 0.62:
            new_status = "probably_sufficient"
        elif old_status == "pending":
            new_status = "listening"

        # Only update if status changed
        if new_status == old_status:
            return None

        # Update card state
        card_state.status = new_status
        card_state.confidence = sufficiency_score
        card_state.evidence_transcript = utterance_text
        card_state.evidence = {
            'judgment': judgment,
            'utterance_id': utterance_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        card_state.updated_at = datetime.utcnow()

        # Set answered_at when becoming sufficient
        if new_status in ["sufficient", "probably_sufficient"] and old_status not in ["sufficient", "probably_sufficient"]:
            card_state.answered_at = datetime.utcnow()

        logger.info(
            f"Updated card state for question '{card.question_text[:30]}...': "
            f"{old_status} -> {new_status} (score: {sufficiency_score:.2f})"
        )

        return {
            'card_id': card.id,
            'card_state_id': card_state.id,
            'old_status': old_status,
            'new_status': new_status,
            'confidence': sufficiency_score,
            'judgment': judgment
        }


# Singleton instance
answer_evaluation_engine = AnswerEvaluationEngine()
