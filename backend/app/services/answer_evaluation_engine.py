"""Answer Evaluation Engine - Core service for evaluating answer sufficiency."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import re
import json
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

            is_interviewer = (speaker != "interviewee")
            if is_interviewer:
                updates = self._process_interviewer_question(
                    db=db,
                    session_id=session_id,
                    section_id=section_id,
                    utterance_text=utterance_text,
                )
                logger.info("Processed interviewer utterance: %s cards updated", len(updates))
                return updates

            # Stage 1: Load only the active card. A completed utterance should
            # advance the question that was just asked, not every pending card
            # in the same interview unit. If partial matching already completed
            # the active card, there may be no listening card left; in that case
            # this completed utterance is intentionally ignored.
            candidate_cards = self._load_candidate_cards(
                db,
                session_id,
                section_id,
                statuses=['listening'],
            )
            if not candidate_cards:
                logger.info("No active listening card found for completed utterance; skipping")
                return []

            logger.info(f"Found {len(candidate_cards)} candidate cards")

            # Bound completed-answer evaluation to the current active question.
            # Older answers from previous questions must not complete the card
            # that was just asked.
            recent_context = self._get_answer_context_for_cards(
                db,
                session_id,
                section_id,
                utterance_text,
                candidate_cards,
            )
            logger.info(f"Using context window: {len(recent_context)} chars")

            # Stage 2: Batch AI sufficiency scoring — one GPT call for all cards
            judgments = self._batch_judge_answer_sufficiency(
                recent_context, candidate_cards, session_id=session_id
            )

            updates = []
            for card_data, judgment in zip(candidate_cards, judgments):
                card = card_data['card']
                card_state = card_data['state']

                update = self._update_card_state(
                    db=db,
                    card_state=card_state,
                    card=card,
                    utterance_id=utterance_id,
                    utterance_text=utterance_text,
                    judgment=judgment,
                    is_interviewer=is_interviewer,
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
        speaker: str = "interviewee",
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

            candidate_cards = self._load_candidate_cards(
                db,
                session_id,
                section_id,
                active_card_id=active_card_id,
                statuses=['listening'],
            )
            if not candidate_cards:
                logger.info("No active card found for partial transcript")
                return []

            judgments = self._batch_judge_answer_sufficiency(
                transcript_text,
                candidate_cards,
                session_id=session_id,
            )

            updates = []
            for card_data, judgment in zip(candidate_cards, judgments):
                update = self._update_card_state(
                    db=db,
                    card_state=card_data['state'],
                    card=card_data['card'],
                    utterance_id=temp_utterance_id,
                    utterance_text=transcript_text,
                    judgment=judgment,
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

    def _process_interviewer_question(
        self,
        db: Session,
        session_id: str,
        section_id: str,
        utterance_text: str,
    ) -> List[Dict[str, Any]]:
        """Mark the best matching card active when the interviewer asks it.

        Interviewer speech should orient the UI only. It must not increase
        answer confidence or become BRD evidence.
        """
        candidate_cards = self._load_candidate_cards(
            db,
            session_id,
            section_id,
            statuses=[
                'pending',
                'listening',
                'probably_sufficient',
                'sufficient',
                'covered',
                'at_risk',
                'manually_checked',
            ],
        )
        if not candidate_cards:
            return []

        best_match = self._find_best_interviewer_card_match(
            utterance_text,
            candidate_cards,
            session_id=session_id,
        )
        if not best_match:
            logger.info("No active card matched interviewer question")
            return []

        card = best_match["card"]
        state = best_match["state"]
        if state.status in ('sufficient', 'covered', 'manually_checked'):
            logger.info(
                "Interviewer question matched completed card '%s...'; active card unchanged",
                card.question_text[:30],
            )
            return []

        updates = []

        for card_info in candidate_cards:
            other_card = card_info["card"]
            other_state = card_info["state"]
            if other_card.id == card.id or other_state.status != "listening":
                continue

            old_status = other_state.status
            other_state.status = "pending"
            other_state.updated_at = datetime.utcnow()
            updates.append({
                "card_id": other_card.id,
                "old_status": old_status,
                "new_status": other_state.status,
                "confidence": float(other_state.confidence or 0),
                "evidence": {
                    "source": "interviewer_question",
                    "activeOnly": True,
                    "deactivated": True,
                },
                "evidence_transcript": other_state.evidence_transcript,
            })

        old_status = state.status
        current_confidence = float(state.confidence or 0)
        state.status = "listening"
        state.updated_at = datetime.utcnow()
        state.evidence = {
            **(state.evidence or {}),
            'activeSource': 'interviewer_question',
            'activeTranscript': utterance_text,
            'activeAt': datetime.utcnow().isoformat(),
        }
        db.commit()

        logger.info(
            "Interviewer question activated card '%s...' without progress",
            card.question_text[:30],
        )
        updates.append({
            "card_id": card.id,
            "old_status": old_status,
            "new_status": state.status,
            "confidence": current_confidence,
            "evidence": {
                "source": "interviewer_question",
                "matchedTranscript": utterance_text,
                "activeOnly": True,
            },
            "evidence_transcript": state.evidence_transcript,
        })
        return updates

    def _find_best_interviewer_card_match(
        self,
        utterance_text: str,
        candidate_cards: List[Dict[str, Any]],
        session_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        semantic_match = self._semantic_interviewer_card_match(
            utterance_text,
            candidate_cards,
            session_id=session_id,
        )
        if semantic_match:
            return semantic_match

        return self._deterministic_interviewer_card_match(utterance_text, candidate_cards)

    def _semantic_interviewer_card_match(
        self,
        utterance_text: str,
        candidate_cards: List[Dict[str, Any]],
        session_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if len(candidate_cards) < 2:
            return None

        try:
            from app.services.openai_service import openai_service
            from app.services.billing_service import billing_service

            model = "gpt-5.4-mini"
            card_lines = []
            card_by_id = {}
            for index, card_info in enumerate(candidate_cards):
                card = card_info["card"]
                state = card_info["state"]
                coverage_rule = question_card_service.normalize_coverage_rule_for_important_elements(
                    getattr(card, 'coverage_rule', None) or {}
                )
                elements = coverage_rule.get('mustMentionElements', []) or []
                element_texts = []
                for element in elements[:5]:
                    if isinstance(element, dict):
                        text = element.get('text')
                    else:
                        text = str(element)
                    if text:
                        element_texts.append(text)

                card_by_id[card.id] = card_info
                card_lines.append(
                    "\n".join([
                        f"{index}. card_id={card.id}",
                        f"status={state.status}",
                        f"focus={card.focus_text or ''}",
                        f"question={card.question_text or ''}",
                        f"required_elements={element_texts}",
                        f"expected_keywords={coverage_rule.get('expectedKeywords', []) or []}",
                    ])
                )

            prompt = (
                "請用語意判斷訪問者剛剛問的是哪一張訪談問題卡。\n"
                "不要使用字面重疊作為主要依據，要判斷問題意圖。\n\n"
                "判斷規則：\n"
                "- 目標/目的/想解決什麼問題，通常對應目標卡。\n"
                "- 支援哪些需求、範圍、邊界、情境、不支援什麼，通常對應範圍卡。\n"
                "- 優先順序、先做哪些功能、MVP、實施先後，通常對應優先級卡。\n"
                "- 若訪問者明確重問已完成卡，仍可選已完成卡；系統會維持不推進。\n"
                "- 若已完成卡與未完成卡字面很像，但訪問者問的是新的子題，請選未完成的新子題卡。\n"
                "- 若只是口頭轉場、沒有對應任何卡，card_id 回傳 null。\n\n"
                f"訪問者問題：{utterance_text}\n\n"
                "候選卡：\n"
                f"{chr(10).join(card_lines)}\n\n"
                "請只回覆 JSON："
                "{\"card_id\": string 或 null, \"confidence\": 0.0-1.0, \"reason\": \"簡短原因\"}"
            )

            response = openai_service.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是訪談問題卡語意匹配器。只回傳 JSON，不要輸出額外文字。"
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            billing_service.record_chat_completion(
                presentation_session_id=session_id,
                operation="interviewer_card_semantic_match",
                model=model,
                response=response,
            )

            content = response.choices[0].message.content or "{}"
            result = json.loads(content)
            card_id = result.get("card_id")
            confidence = float(result.get("confidence", 0) or 0)
            reason = result.get("reason", "")

            logger.info(
                "AI interviewer card match: card_id=%s confidence=%.2f reason=%s",
                card_id,
                confidence,
                reason,
            )

            if not card_id or confidence < 0.45:
                return None

            return card_by_id.get(card_id)
        except Exception as exc:
            logger.warning("AI interviewer card match failed; falling back to deterministic matcher: %s", exc)
            return None

    def _deterministic_interviewer_card_match(
        self,
        utterance_text: str,
        candidate_cards: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        scored = [
            (self._score_interviewer_card_match(utterance_text, card_info["card"]), card_info)
            for card_info in candidate_cards
        ]
        if not scored:
            return None

        top_scores = sorted(scored, key=lambda item: item[0], reverse=True)[:3]
        logger.info(
            "Interviewer card match candidates: %s",
            [
                {
                    "score": round(candidate_score, 3),
                    "card_id": candidate_info["card"].id,
                    "question": (candidate_info["card"].question_text or "")[:40],
                }
                for candidate_score, candidate_info in top_scores
            ],
        )
        score, card_info = top_scores[0]
        if score < 0.18:
            return None

        state = card_info["state"]
        if state.status not in ('sufficient', 'covered', 'manually_checked'):
            return card_info

        for candidate_score, candidate_info in top_scores[1:]:
            candidate_state = candidate_info["state"]
            if candidate_state.status in ('sufficient', 'covered', 'manually_checked'):
                continue
            if candidate_score >= 0.18 and candidate_score >= score - 0.03:
                logger.info(
                    "Interviewer question preferred unfinished card '%s...' over completed tie '%s...'",
                    candidate_info["card"].question_text[:30],
                    card_info["card"].question_text[:30],
                )
                return candidate_info

        return card_info

    def _score_interviewer_card_match(self, utterance_text: str, card: QuestionCard) -> float:
        utterance = self._normalize_match_text(utterance_text)
        if not utterance:
            return 0.0

        coverage_rule = question_card_service.normalize_coverage_rule_for_important_elements(
            getattr(card, 'coverage_rule', None) or {}
        )
        texts = [card.question_text or "", card.focus_text or ""]
        texts.extend(coverage_rule.get('expectedKeywords', []) or [])
        for element in coverage_rule.get('mustMentionElements', []) or []:
            if isinstance(element, dict):
                texts.append(element.get('text') or "")
                texts.extend(element.get('aliases') or [])
            else:
                texts.append(str(element))

        texts = self._expand_interviewer_match_texts(texts)
        best_score = 0.0
        utterance_bigrams = self._text_bigrams(utterance)
        for text in texts:
            candidate = self._normalize_match_text(text)
            if len(candidate) < 2:
                continue
            if candidate in utterance or utterance in candidate:
                best_score = max(best_score, 1.0)
                continue

            candidate_bigrams = self._text_bigrams(candidate)
            if not candidate_bigrams:
                continue
            overlap = len(utterance_bigrams & candidate_bigrams)
            denominator = max(1, min(len(utterance_bigrams), len(candidate_bigrams)))
            best_score = max(best_score, overlap / denominator)

        candidate_corpus = self._normalize_match_text(" ".join(texts))
        adjusted_score = best_score + self._intent_match_adjustment(utterance, candidate_corpus)
        return max(0.0, min(1.0, adjusted_score))

    def _expand_interviewer_match_texts(self, texts: List[str]) -> List[str]:
        """Add local UI phrasing aliases for interviewer question matching."""
        expanded = list(texts)
        normalized_corpus = self._normalize_match_text(" ".join(texts))

        if self._contains_any(normalized_corpus, ["目標", "目的"]):
            expanded.extend([
                "這個需求訪談助手第一階段最想解決的是什麼問題",
                "需求訪談助手在第一個階段想要解決的是什麼問題",
                "需求訪談助手的業務目標",
                "第一階段主要目標",
            ])

        if self._contains_any(normalized_corpus, ["範圍", "支援", "邊界"]):
            expanded.extend([
                "這個助手第一階段主要支援哪些需求訪談情境",
                "需求訪談助手支援哪些需求範圍",
                "哪些情境先不納入",
                "支援範圍與邊界",
            ])

        return expanded

    def _intent_match_adjustment(self, utterance: str, candidate_corpus: str) -> float:
        """Separate nearby interview intents such as goal vs. support scope."""
        goal_terms = [
            "目標",
            "目的",
            "解決",
            "想解決",
            "想要解決",
            "達到",
            "希望",
            "期待",
            "業務目標",
        ]
        scope_terms = [
            "範圍",
            "支援",
            "不支援",
            "不納入",
            "排除",
            "邊界",
            "情境",
            "需求訪談情境",
            "哪些需求",
            "哪些情境",
        ]

        utterance_is_goal = self._contains_any(utterance, goal_terms)
        utterance_is_scope = self._contains_any(utterance, scope_terms)
        card_is_goal = self._contains_any(candidate_corpus, goal_terms)
        card_is_scope = self._contains_any(candidate_corpus, scope_terms)

        adjustment = 0.0
        if utterance_is_goal and card_is_goal:
            adjustment += 0.35
        if utterance_is_goal and card_is_scope and not utterance_is_scope:
            adjustment -= 0.3
        if utterance_is_scope and card_is_scope:
            adjustment += 0.35
        if utterance_is_scope and card_is_goal and not utterance_is_goal:
            adjustment -= 0.2

        return adjustment

    def _contains_any(self, text: str, terms: List[str]) -> bool:
        return any(self._normalize_match_text(term) in text for term in terms)

    @staticmethod
    def _normalize_match_text(text: str) -> str:
        return re.sub(r"[\W_]+", "", (text or "").lower())

    @staticmethod
    def _text_bigrams(text: str) -> set[str]:
        if len(text) < 2:
            return set()
        return {text[index:index + 2] for index in range(len(text) - 1)}

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

        session = db.query(InterviewSession).filter(
            InterviewSession.id == session_id
        ).first()

        if not session:
            return []

        from sqlalchemy import or_
        # Get question cards matching by theme_id or section_id
        cards = db.query(QuestionCard).filter(
            QuestionCard.document_id == session.document_id,
            or_(
                QuestionCard.interview_theme_id == section_id,
                QuestionCard.section_id == section_id,
            )
        ).all()
        if active_card_id:
            cards = [card for card in cards if card.id == active_card_id]
        if not cards:
            return []

        # Get their states
        card_states = db.query(InterviewCardState).filter(
            InterviewCardState.session_id == session_id,
            InterviewCardState.question_card_id.in_([card.id for card in cards]),
            InterviewCardState.status.in_(statuses or ['pending', 'listening', 'probably_sufficient', 'at_risk'])
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

    def _get_answer_context_for_cards(
        self,
        db: Session,
        session_id: str,
        section_id: str,
        current_text: str,
        candidate_cards: List[Dict[str, Any]],
        max_chars: int = 2000,
    ) -> str:
        """Build answer context within the boundary of the active question.

        The active boundary is set when an interviewer utterance marks a card as
        listening. Completed utterances should only be judged with interviewee
        speech after that point, so prior answers in the same section cannot
        accidentally complete the current card.
        """
        active_since = self._latest_active_at(candidate_cards)
        if not active_since:
            logger.info("No active question boundary found; using current completed utterance only")
            return current_text

        bounded_context = self._get_recent_context_since(
            db=db,
            session_id=session_id,
            section_id=section_id,
            current_text=current_text,
            since=active_since,
            max_chars=max_chars,
        )
        logger.info("Bounded answer context since active question at %s", active_since.isoformat())
        return bounded_context

    def _get_recent_context_since(
        self,
        db: Session,
        session_id: str,
        section_id: str,
        current_text: str,
        since: datetime,
        max_chars: int = 2000,
    ) -> str:
        """Get interviewee context after a question boundary."""
        recent_utterances = db.query(Utterance).filter(
            Utterance.session_id == session_id,
            Utterance.section_id == section_id,
            Utterance.speaker == "interviewee",
            Utterance.created_at >= since,
        ).order_by(
            Utterance.created_at.desc()
        ).limit(10).all()

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

    def _latest_active_at(self, candidate_cards: List[Dict[str, Any]]) -> Optional[datetime]:
        active_times = []
        for card_info in candidate_cards:
            state = card_info.get("state")
            evidence = getattr(state, "evidence", None) or {}
            active_at = evidence.get("activeAt") if isinstance(evidence, dict) else None
            parsed = self._parse_iso_datetime(active_at)
            if parsed:
                active_times.append(parsed)

        return max(active_times) if active_times else None

    @staticmethod
    def _parse_iso_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

    def _batch_judge_answer_sufficiency(
        self,
        context: str,
        candidate_cards: List[Dict[str, Any]],
        session_id: str
    ) -> List[Dict[str, Any]]:
        """Batch judge all cards in a single GPT call."""
        import json
        from app.services.openai_service import openai_service

        cards_description = []
        for i, card_data in enumerate(candidate_cards):
            card = card_data['card']
            coverage_rule = question_card_service.normalize_coverage_rule_for_important_elements(
                getattr(card, 'coverage_rule', None) or {}
            )
            expected_keywords = coverage_rule.get('expectedKeywords', []) or []
            must_mention_elements = coverage_rule.get('mustMentionElements', []) or []
            semantic_anchors = coverage_rule.get('semanticAnchors', []) or []
            element_lines = []
            for element_index, element in enumerate(must_mention_elements):
                if isinstance(element, dict):
                    text = element.get('text')
                    aliases = element.get('aliases') or []
                else:
                    text = str(element)
                    aliases = []
                if text:
                    alias_text = f" aliases={aliases}" if aliases else ""
                    element_lines.append(f"element_{element_index}: {text}{alias_text}")

            cards_description.append(
                "\n".join([
                    f"{i}: focus=\"{card.focus_text or card.question_text}\"",
                    f"question=\"{card.question_text}\"",
                    f"required_elements={element_lines}",
                    f"expected_keywords={expected_keywords}",
                    f"semantic_anchors={semantic_anchors}",
                ])
            )

        cards_list = "\n".join(cards_description)

        try:
            response = openai_service.client.chat.completions.create(
                model="gpt-5.4-mini",
                messages=[
                    {"role": "system", "content": (
                        "你是 BRD 訪談評估系統。判斷受訪者的回答是否充分回應了每個提問重點。\n"
                        "對每張卡片回傳 confidence（0.0-1.0）：\n"
                        "- 0.0-0.3：完全沒提到相關內容\n"
                        "- 0.3-0.6：稍微提及但不足以寫入 BRD\n"
                        "- 0.6-0.8：有實質內容，可作為 BRD 素材\n"
                        "- 0.8-1.0：充分回答，足以產出正式 BRD 段落\n\n"
                        "Return valid JSON only. 回傳格式必須是 JSON：\n"
                        "{\"cards\": [{\"confidence\": 0.5, \"is_covered\": false, \"covered_element_ids\": [\"element_0\"], \"missing_element_ids\": [\"element_1\"], \"reason\": \"...\", \"suggested_followup\": \"...\"}]}\n"
                        "若回答不足，suggested_followup 請根據 missing_element_ids 和 reason 產生一題可直接詢問受訪者的追問；若已充分回答則回傳空字串。\n"
                        "cards 陣列的長度必須等於提問重點卡片的數量，順序一一對應。"
                    )},
                    {"role": "user", "content": (
                        f"受訪者說的話：\n{context[:2000]}\n\n"
                        f"提問重點卡片（共 {len(candidate_cards)} 張）：\n{cards_list}\n\n"
                        f"請為每張卡片評分，回傳 {len(candidate_cards)} 個結果。只輸出 JSON。"
                    )},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            result = json.loads(content)
            logger.info(f"Batch judgment raw response: {content[:300]}")

            # Parse result — handle various response formats
            if isinstance(result, list):
                judgments_raw = result
            else:
                # Try common wrapper keys
                for key in ["cards", "results", "judgments", "evaluations"]:
                    if key in result and isinstance(result[key], list):
                        judgments_raw = result[key]
                        break
                else:
                    judgments_raw = []

            judgments = []
            for i in range(len(candidate_cards)):
                if i < len(judgments_raw):
                    item = judgments_raw[i]
                    judgments.append({
                        "confidence": item.get("confidence", 0.0),
                        "is_covered": item.get("is_covered", False),
                        "covered_element_ids": item.get("covered_element_ids", []) or [],
                        "missing_element_ids": item.get("missing_element_ids", []) or [],
                        "reason": item.get("reason", ""),
                        "suggested_followup": item.get("suggested_followup", "") or "",
                    })
                else:
                    judgments.append({"confidence": 0.0, "is_covered": False, "suggested_followup": ""})

            logger.info(f"Batch judgment for {len(candidate_cards)} cards: {[j['confidence'] for j in judgments]}")
            return judgments

        except Exception as e:
            logger.error(f"Batch judgment failed: {e}", exc_info=True)
            # Fallback: return zeros
            return [{"confidence": 0.0, "is_covered": False}] * len(candidate_cards)

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
        judgment: Dict[str, Any],
        is_interviewer: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Update card state based on sufficiency judgment."""
        old_status = card_state.status
        # Don't downgrade already completed cards
        if old_status in ('sufficient', 'covered', 'manually_checked'):
            return None

        ai_confidence = judgment.get('sufficiency_score', None) or judgment.get('confidence', 0.0)
        is_covered = judgment.get('is_sufficient', None) or judgment.get('is_covered', False)
        current_confidence = float(card_state.confidence or 0)
        covered_element_ids = set(judgment.get('covered_element_ids', []) or [])
        missing_element_ids = set(judgment.get('missing_element_ids', []) or [])
        if covered_element_ids or missing_element_ids:
            covered, missing = self._normalize_completion_element_ids(
                card=card,
                completion={
                    'covered_element_ids': list(covered_element_ids),
                    'missing_element_ids': list(missing_element_ids),
                },
                completion_percentage=ai_confidence * 100,
                is_sufficient=bool(is_covered),
            )
        else:
            covered, missing = [], []

        if ai_confidence < 0.3:
            return None

        if is_interviewer:
            new_confidence = min(current_confidence + 0.05, 0.15)
            new_status = "listening" if old_status == "pending" else old_status
        else:
            new_confidence = max(current_confidence, ai_confidence)
            if is_covered or ai_confidence >= 0.85:
                new_status = "sufficient"
            elif ai_confidence >= 0.62:
                new_status = "probably_sufficient"
            elif old_status == "pending":
                new_status = "listening"
            else:
                new_status = old_status

        # Only update if something changed
        if new_status == old_status and new_confidence <= current_confidence:
            return None

        # Update card state
        card_state.status = new_status
        card_state.confidence = new_confidence
        if not is_interviewer:
            existing_evidence = card_state.evidence_transcript or ""
            card_state.evidence_transcript = f"{existing_evidence}\n{utterance_text}".strip()
        judgment = self._preserve_existing_followup_when_empty(card_state.evidence, judgment)
        card_state.evidence = {
            'judgment': judgment,
            'utterance_id': utterance_id,
            'accumulated_confidence': new_confidence,
            'matchedTranscript': utterance_text,
            'coveredElementIds': covered,
            'missingElementIds': missing,
            'coveredAspectIds': covered,
            'timestamp': datetime.utcnow().isoformat()
        }
        card_state.updated_at = datetime.utcnow()

        # Set answered_at when becoming sufficient
        if new_status in ["sufficient", "probably_sufficient"] and old_status not in ["sufficient", "probably_sufficient"]:
            card_state.answered_at = datetime.utcnow()

        logger.info(
            f"Updated card state for question '{card.question_text[:30]}...': "
            f"{old_status} -> {new_status} (score: {ai_confidence:.2f})"
        )

        return {
            'card_id': card.id,
            'card_state_id': card_state.id,
            'old_status': old_status,
            'new_status': new_status,
            'confidence': new_confidence,
            'evidence': card_state.evidence,
            'evidence_transcript': card_state.evidence_transcript,
            'judgment': judgment
        }

    def _preserve_existing_followup_when_empty(
        self,
        existing_evidence: Optional[Dict[str, Any]],
        judgment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Keep the last useful follow-up when a later judgment returns an empty one."""
        next_followup = (
            judgment.get("suggested_followup")
            or judgment.get("suggestedFollowup")
            or ""
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


# Singleton instance
answer_evaluation_engine = AnswerEvaluationEngine()
