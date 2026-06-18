"""Answer Evaluation Engine - Core service for evaluating answer sufficiency."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from sqlalchemy.orm import Session

from app.services.question_card_service import question_card_service
from app.services.question_rubric_service import question_rubric_service
from app.services.answer_completion_scorer import answer_completion_scorer
from app.models.question_card import QuestionCard
from app.models.interview_session import InterviewCardState
from app.models.live_utterance import LiveUtterance
from app.models.card_coverage_evaluation import CardCoverageEvaluation

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
        max_seq = db.query(CardCoverageEvaluation).filter(
            CardCoverageEvaluation.session_id == session_id,
            CardCoverageEvaluation.card_id == card_id,
        ).with_entities(CardCoverageEvaluation.evaluation_seq).order_by(
            CardCoverageEvaluation.evaluation_seq.desc()
        ).first()

        return (max_seq[0] + 1) if max_seq else 1

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
            card,
            set(completion.get('covered_element_ids', []) or [])
        )
        missing_element_ids = self._canonicalize_element_ids(
            card,
            set(completion.get('missing_element_ids', []) or [])
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

            candidate_cards = self._load_candidate_cards(
                db,
                session_id,
                section_id,
                statuses=['pending', 'listening', 'probably_sufficient', 'at_risk'],
            )
            if not candidate_cards:
                logger.info("No candidate cards found for utterance; skipping")
                return []

            logger.info(f"Found {len(candidate_cards)} candidate cards")

            filtered_candidates = self._prefilter_candidates(
                utterance_text,
                candidate_cards,
                top_k=8
            )
            logger.info(f"Prefiltered to {len(filtered_candidates)} candidate cards")

            recent_context = self._build_structured_context(
                db,
                session_id,
                section_id,
                utterance_text,
                filtered_candidates,
            )
            logger.info(f"Using structured context: {len(recent_context)} chars")

            judgments = self._batch_judge_answer_sufficiency(
                recent_context,
                filtered_candidates,
                session_id=session_id,
                model_override="gpt-5.4-mini",
                db=db
            )

            # One utterance should only advance ONE card from pending state.
            # If a card is already listening/probably_sufficient, it can still accumulate.
            # But we don't let one sentence jump multiple pending cards forward at once.
            max_confidence = max((j.get('confidence', 0) for j in judgments), default=0)
            has_advanced_pending = False

            updates = []
            for card_data, judgment in zip(filtered_candidates, judgments):
                card = card_data['card']
                card_state = card_data['state']
                conf = judgment.get('confidence', 0)

                # For pending cards: only advance the highest-scoring one
                if conf > 0 and card_state.status == 'pending':
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

            logger.info(
                "Processed utterance: %s/%s cards updated (from %s candidates)",
                len(updates),
                len(filtered_candidates),
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
                statuses=['listening'],
            )
            if not candidate_cards:
                logger.info("No active card found for partial transcript")
                return []

            judgments = self._batch_judge_answer_sufficiency(
                transcript_text,
                candidate_cards,
                session_id=session_id,
                db=db
            )

            # Phase 2: Cap partial transcript judgments at probably_sufficient
            # Partial transcripts cannot produce "sufficient" state
            for judgment in judgments:
                if judgment.get('is_covered') or judgment.get('is_sufficient'):
                    judgment['is_covered'] = False
                    judgment['is_sufficient'] = False
                    # Cap confidence to prevent sufficient state
                    if judgment.get('confidence', 0) >= 0.85:
                        judgment['confidence'] = 0.80

            updates = []
            for card_data, judgment in zip(candidate_cards, judgments):
                update = self._update_card_state(
                    db=db,
                    card_state=card_data['state'],
                    card=card_data['card'],
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
        text_ngrams = set(text[i:i+n] for i in range(len(text) - n + 1))
        ref_ngrams = set(reference[i:i+n] for i in range(len(reference) - n + 1))
        if not ref_ngrams:
            return 0.0
        return len(text_ngrams & ref_ngrams) / len(ref_ngrams)

    def _prefilter_candidates(
        self,
        utterance_text: str,
        candidate_cards: list,
        top_k: int = 8
    ) -> list:
        """Fast keyword-based prefilter to reduce candidates before LLM call.

        Phase 3: Scores each card by keyword overlap with the utterance text.
        Uses character n-gram overlap for Chinese text matching.
        Returns top-K candidates.
        """
        if len(candidate_cards) <= top_k:
            return candidate_cards

        text_lower = utterance_text.lower()
        scored = []
        for card_data in candidate_cards:
            card = card_data['card']
            score = 0.0

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
            coverage_rule = getattr(card, 'coverage_rule', None) or {}
            keywords = coverage_rule.get('expectedKeywords', []) or []
            for kw in keywords:
                if kw and kw.lower() in text_lower:
                    score += 3.0

            # Check mustMentionElements (substring matching works fine)
            elements = coverage_rule.get('mustMentionElements', []) or []
            for elem in elements:
                elem_text = elem.get('text', '') if isinstance(elem, dict) else str(elem)
                if elem_text and elem_text.lower() in text_lower:
                    score += 2.0

            scored.append((score, card_data))

        # Sort by score descending, take top-K
        scored.sort(key=lambda x: x[0], reverse=True)

        # Always include cards with score > 0, plus fill up to top_k
        result = [item for score, item in scored if score > 0]
        if len(result) < top_k:
            remaining = [item for score, item in scored if score == 0]
            result.extend(remaining[:top_k - len(result)])

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

        # Get their states (exclude role-inapplicable cards)
        excluded_statuses = {'not_applicable_for_role', 'needs_different_stakeholder'}
        card_states = db.query(InterviewCardState).filter(
            InterviewCardState.session_id == session_id,
            InterviewCardState.question_card_id.in_([card.id for card in cards]),
            InterviewCardState.status.in_(statuses or ['pending', 'listening', 'probably_sufficient', 'at_risk']),
            ~InterviewCardState.status.in_(excluded_statuses),
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
        all_utterances = db.query(LiveUtterance).filter(
            LiveUtterance.session_id == session_id,
        ).order_by(LiveUtterance.created_at.asc()).all()

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

        cards_description = []
        for i, card_data in enumerate(candidate_cards):
            card = card_data['card']

            # Get or compile rubric for this card
            rubric = question_rubric_service.get_or_compile_rubric(db, card) if db else {}
            criteria = rubric.get('criteria', [])
            answer_target = rubric.get('answerTarget', card.question_text)

            # Build criteria description for prompt
            criteria_lines = []
            for criterion in criteria:
                crit_id = criterion.get('id', f'criterion_{len(criteria_lines)}')
                desc = criterion.get('description', '')
                crit_type = criterion.get('type', 'value_slot')
                required = '必要' if criterion.get('required') else '選填'
                criteria_lines.append(f"  {crit_id}: {desc} (type={crit_type}, {required})")

            # Include current coverage progress
            state = card_data.get('state')
            current_status = state.status if state else 'pending'
            existing_evidence = getattr(state, 'evidence', None) or {} if state else {}
            already_satisfied = existing_evidence.get('satisfiedCriteria', []) or []

            cards_description.append(
                "\n".join([
                    f"{i}: question=\"{card.question_text}\"",
                    f"focus=\"{card.focus_text or ''}\"",
                    f"answer_target=\"{answer_target}\"",
                    f"criteria:\n" + "\n".join(criteria_lines) if criteria_lines else "criteria: (none)",
                    f"current_status=\"{current_status}\" already_satisfied={already_satisfied}",
                ])
            )

        cards_list = "\n".join(cards_description)

        # New criterion-based system prompt
        system_prompt = (
            "你是 BRD 訪談評估系統。你的任務是逐 criterion 判斷對話是否滿足每張卡片的評估標準。\n\n"
            "【重要】輸入來自即時語音辨識，可能有錯字、漏字、斷句不完整。請根據語意而非字面判斷。\n\n"
            "判斷規則：\n"
            "1. 每張卡片有多個 criteria（評估項目），你必須逐項判斷。\n"
            "2. 只有實質回答（描述具體情況、表達明確觀點、提供資訊）才算滿足 criterion。\n"
            "3. 提問本身（疑問句、請求對方回答）不算滿足任何 criterion。\n"
            "4. 每個 criterion 的 status 必須是以下之一：\n"
            "   - satisfied：已有明確、完整的回答，且有原文引述\n"
            "   - partially_satisfied：有提到但不完整或模糊\n"
            "   - attempted_but_unresolved：受訪者嘗試回答但未能解決（如「不確定」「要再確認」）\n"
            "   - not_addressed：完全未提及\n"
            "   - contradicted：前後矛盾或否定先前的回答\n"
            "   - not_applicable：該 criterion 不適用於此情境\n"
            "5. status 為 satisfied 或 partially_satisfied 時，必須提供 evidence_quotes（原文片段）。\n"
            "6. 沒有原文支持就不能標記 satisfied。\n\n"
            "每張卡片的 relation 欄位判斷：\n"
            "- answer：對話內容是在回答這個問題\n"
            "- tangential：提到了相關主題但不是直接回答\n"
            "- irrelevant：完全無關\n\n"
            "response_status 判斷：\n"
            "- responded：受訪者有給出回應\n"
            "- question_only：只有提問，尚無回應\n"
            "- not_yet：尚未被討論\n\n"
            "resolution_status 判斷：\n"
            "- resolved：問題已被充分回答\n"
            "- partially_resolved：部分回答\n"
            "- unresolved：提了但沒解決\n"
            "- not_started：完全未開始\n\n"
            "回傳格式必須是 JSON：\n"
            "{\"evaluations\": [{\"relation\": \"answer\", \"response_status\": \"responded\", "
            "\"resolution_status\": \"partially_resolved\", "
            "\"criteria\": [{\"criterion_id\": \"criterion_0\", \"status\": \"satisfied\", "
            "\"normalized_value\": \"具體值\", \"evidence_quotes\": [\"原文片段\"], "
            "\"evaluator_confidence\": 0.95, \"reason\": \"判斷理由\"}], "
            "\"suggested_followup\": \"追問建議\"}]}\n\n"
            "重要限制：\n"
            "- evaluations 陣列長度必須等於卡片數量，順序一一對應。\n"
            "- 禁止輸出 completion_score 或 is_sufficient（由程式計算）。\n"
            "- 每句話通常只對應 0 或 1 張卡片。relation 為 answer 的卡片不應超過 1 張。\n"
            "- 判斷時要看整段累計對話，不只看最新一句。\n"
            "- suggested_followup 必須問尚未被回答的部分，不要重複已回答內容。\n"
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
                        judgments_raw = [result[str(i)] for i in range(len(candidate_cards)) if str(i) in result]
                    else:
                        judgments_raw = []

            judgments = []
            for i in range(len(candidate_cards)):
                if i < len(judgments_raw):
                    item = judgments_raw[i]
                    criterion_evals = item.get('criteria', []) or []

                    # Get rubric for this card to calculate completion
                    card = candidate_cards[i]['card']
                    rubric = question_rubric_service.get_or_compile_rubric(db, card) if db else {}
                    rubric_criteria = rubric.get('criteria', [])

                    # Use deterministic scorer
                    completion_score = answer_completion_scorer.calculate_completion(
                        rubric_criteria, criterion_evals
                    )
                    is_sufficient = answer_completion_scorer.is_sufficient(
                        rubric_criteria, criterion_evals, completion_score
                    )

                    evidence_quote = ''
                    for e in criterion_evals:
                        if e.get('evidence_quotes'):
                            evidence_quote = e['evidence_quotes'][0]
                            break

                    # Ensure card activation even when completion=0 but topic was touched
                    relation = item.get("relation", "irrelevant")
                    response_status = item.get("response_status", "not_yet")
                    effective_confidence = completion_score
                    if effective_confidence == 0 and relation in ("answer", "tangential"):
                        effective_confidence = 0.01  # activate card (listening)
                    if effective_confidence == 0 and response_status == "question_only":
                        effective_confidence = 0.01

                    judgments.append({
                        "confidence": effective_confidence,
                        "is_covered": is_sufficient,
                        "relation": relation,
                        "response_status": response_status,
                        "resolution_status": item.get("resolution_status", "not_started"),
                        "criterion_evaluations": criterion_evals,
                        "covered_element_ids": [
                            e['criterion_id'] for e in criterion_evals
                            if e.get('status') == 'satisfied'
                        ],
                        "missing_element_ids": [
                            e['criterion_id'] for e in criterion_evals
                            if e.get('status') in ('not_addressed', 'attempted_but_unresolved', 'partially_satisfied')
                        ],
                        "reason": "; ".join(e.get('reason', '') for e in criterion_evals if e.get('reason')),
                        "suggested_followup": item.get("suggested_followup", "") or "",
                        "evidence_quote": evidence_quote,
                    })
                else:
                    judgments.append({
                        "confidence": 0.0,
                        "is_covered": False,
                        "relation": "irrelevant",
                        "response_status": "not_yet",
                        "criterion_evaluations": [],
                        "suggested_followup": "",
                        "evidence_quote": "",
                    })

            logger.info(f"Batch judgment for {len(candidate_cards)} cards: {[j['confidence'] for j in judgments]}")
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

        # Deterministic reducer — no speaker distinction.
        # Any utterance that touches a card's topic triggers state change.
        new_status, new_confidence = self._reduce_state(
            current_status=old_status,
            judgment=judgment,
            is_partial=is_partial
        )
        # Confidence logic: always accumulate upward (never decrease)
        if new_status == 'pending':
            new_confidence = current_confidence
        else:
            new_confidence = max(current_confidence, new_confidence)

        # Always write CardCoverageEvaluation for traceability (even if no state change)
        evaluation_seq = self._get_next_evaluation_seq(db, card_state.session_id, card.id)
        covered, missing = [], []
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

        coverage_eval = CardCoverageEvaluation(
            id=f"cce_{uuid.uuid4().hex[:12]}",
            session_id=card_state.session_id,
            card_id=card.id,
            basis_type="live",
            transcript_revision_id=None,
            state=new_status,
            confidence=ai_confidence,
            covered_element_ids=covered or [],
            missing_element_ids=missing or [],
            evidence=[{"evidence_quote": judgment.get("evidence_quote", "")}] if judgment.get("evidence_quote") else [],
            evaluation_seq=evaluation_seq,
            model=model_used,
            prompt_version=None,
            created_at=datetime.utcnow(),
        )
        db.add(coverage_eval)

        # No meaningful progress — skip UI update but evaluation is still recorded
        if new_status == old_status and new_confidence <= current_confidence and ai_confidence <= current_confidence:
            return None

        # Update card state
        card_state.status = new_status
        card_state.confidence = new_confidence
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
            'satisfiedCriteria': [
                e['criterion_id'] for e in judgment.get('criterion_evaluations', [])
                if e.get('status') == 'satisfied'
            ],
            'criterionEvaluations': judgment.get('criterion_evaluations', []),
            'coveredAspectIds': covered,
            'timestamp': datetime.utcnow().isoformat()
        }
        card_state.updated_at = datetime.utcnow()

        # Set answered_at when becoming sufficient
        if new_status in ["sufficient", "probably_sufficient"] and old_status not in ["sufficient", "probably_sufficient"]:
            card_state.answered_at = datetime.utcnow()

        logger.info(
            f"Updated card state for question '{card.question_text[:30]}...': "
            f"{old_status} -> {new_status} (score: {ai_confidence:.2f}, seq: {evaluation_seq})"
        )

        return {
            'card_id': card.id,
            'card_state_id': card_state.id,
            'old_status': old_status,
            'new_status': new_status,
            'confidence': new_confidence,
            'evidence': card_state.evidence,
            'evidence_transcript': card_state.evidence_transcript,
            'judgment': judgment,
            'evaluation_seq': evaluation_seq,
        }

    def _reduce_state(
        self,
        current_status: str,
        judgment: dict,
        is_partial: bool = False
    ) -> tuple[str, float]:
        """Deterministic state reducer. Returns (new_status, capped_confidence).

        State machine:
        - confidence > 0 but no covered elements → listening (highlighted, progress=0)
        - confidence > 0 with covered elements → progress starts (probably_sufficient)
        - all elements covered + evidence → sufficient

        Constraints:
        - partial transcript cannot produce 'sufficient'
        - No evidence_quote cannot produce 'sufficient'
        - missing required elements cannot produce 'sufficient'
        - State can only move forward (pending→listening→probably_sufficient→sufficient)
        """
        confidence = judgment.get('confidence', 0.0)
        is_covered = judgment.get('is_covered', False)
        has_evidence = bool(judgment.get('evidence_quote'))
        missing = judgment.get('missing_element_ids', [])
        _ = judgment.get('covered_element_ids', [])

        # Determine target state
        if confidence <= 0:
            # 0 = completely unrelated → stay pending
            target = 'pending'
        elif confidence <= 0.25:
            # 0.01-0.25 = card activated (question asked, or very early/vague mention) → listening
            target = 'listening'
        elif confidence < 0.7:
            # 0.26-0.69 = partial answer accumulating → probably_sufficient (progress bar moves)
            target = 'probably_sufficient'
        elif is_covered and has_evidence and not missing and confidence >= 0.7:
            # >= 0.7 with evidence + is_covered + no missing elements = sufficient (complete)
            target = 'sufficient'
        else:
            target = 'probably_sufficient'

        # Constraints
        if is_partial and target == 'sufficient':
            target = 'probably_sufficient'
            confidence = min(confidence, 0.80)

        if not has_evidence and target == 'sufficient':
            target = 'probably_sufficient'

        # State can only move forward
        STATE_ORDER = {'pending': 0, 'listening': 1, 'probably_sufficient': 2, 'sufficient': 3}
        current_order = STATE_ORDER.get(current_status, 0)
        target_order = STATE_ORDER.get(target, 0)

        if target_order < current_order:
            target = current_status

        return target, confidence

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
        from app.models.interview_session import InterviewSession
        from app.models.final_utterance import FinalUtterance
        from app.models.question_card import QuestionCard
        from app.models.interview_theme import InterviewTheme

        logger.info(f"Running final coverage evaluation for session {session_id}")

        # Load session
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            logger.error(f"Session {session_id} not found")
            return []

        # Load all final utterances for this revision
        final_utterances = db.query(FinalUtterance).filter(
            FinalUtterance.session_id == session_id,
            FinalUtterance.transcript_revision_id == transcript_revision_id,
        ).order_by(FinalUtterance.sequence_index).all()

        if not final_utterances:
            logger.warning(f"No final utterances found for session {session_id}")
            return []

        # Load all question cards for this document
        themes = db.query(InterviewTheme).filter(
            InterviewTheme.document_id == session.document_id,
            InterviewTheme.is_enabled == True,
        ).order_by(InterviewTheme.order_index).all()

        all_cards = []
        for theme in themes:
            cards = db.query(QuestionCard).filter(
                QuestionCard.interview_theme_id == theme.id,
            ).order_by(QuestionCard.order_index).all()
            for card in cards:
                all_cards.append({
                    'card': card,
                    'theme_id': theme.id,
                    'theme_title': theme.title,
                })

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
            full_transcript,
            all_cards,
            session_id=session_id,
            db=db
        )

        # Write CardCoverageEvaluation records with basis_type='final'
        results = []
        for card_data, judgment in zip(all_cards, judgments):
            card = card_data['card']

            # Determine state based on judgment
            ai_confidence = judgment.get('sufficiency_score', None) or judgment.get('confidence', 0.0)
            is_covered = judgment.get('is_sufficient', None) or judgment.get('is_covered', False)
            covered_element_ids = judgment.get('covered_element_ids', []) or []
            missing_element_ids = judgment.get('missing_element_ids', []) or []

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

            # Determine state using the same _reduce_state() method for consistency
            state, _ = self._reduce_state(
                current_status='pending',
                judgment={
                    'confidence': ai_confidence,
                    'is_covered': is_covered,
                    'evidence_quote': judgment.get('evidence_quote', ''),
                    'missing_element_ids': missing,
                    'covered_element_ids': covered,
                },
                is_partial=False
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

            results.append({
                'card_id': card.id,
                'state': state,
                'confidence': ai_confidence,
                'covered_element_ids': covered,
                'missing_element_ids': missing,
                'evaluation_seq': evaluation_seq,
            })

        db.commit()
        logger.info(f"Final coverage complete: wrote {len(results)} evaluations")

        return results


# Singleton instance
answer_evaluation_engine = AnswerEvaluationEngine()
