"""Answer Evaluation Engine - Core service for evaluating answer sufficiency."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import re
import json
import uuid
from sqlalchemy.orm import Session

from app.services.embedding_service import embedding_service
from app.services.scoring_service import scoring_service
from app.services.semantic_judge_service import semantic_judge_service
from app.services.question_card_service import question_card_service
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
        self.embedding_service = embedding_service
        self.scoring_service = scoring_service
        self.semantic_judge = semantic_judge_service

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

            candidate_cards = self._load_candidate_cards(
                db,
                session_id,
                section_id,
                statuses=['listening', 'pending'],
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
                model_override="gpt-5.4-mini"
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


    def _prefilter_candidates(
        self,
        utterance_text: str,
        candidate_cards: list,
        top_k: int = 8
    ) -> list:
        """Fast keyword-based prefilter to reduce candidates before LLM call.

        Phase 3: Scores each card by keyword overlap with the utterance text.
        Returns top-K candidates.
        """
        if len(candidate_cards) <= top_k:
            return candidate_cards

        text_lower = utterance_text.lower()
        scored = []
        for card_data in candidate_cards:
            card = card_data['card']
            score = 0.0

            # Check focus_text overlap
            if card.focus_text and any(w in text_lower for w in card.focus_text.lower().split() if len(w) > 2):
                score += 2.0

            # Check question_text overlap
            if card.question_text and any(w in text_lower for w in card.question_text.lower().split() if len(w) > 2):
                score += 1.0

            # Check expectedKeywords from coverage_rule
            coverage_rule = getattr(card, 'coverage_rule', None) or {}
            keywords = coverage_rule.get('expectedKeywords', []) or []
            for kw in keywords:
                if kw and kw.lower() in text_lower:
                    score += 3.0

            # Check mustMentionElements
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
        section_id: str,
        current_text: str,
        candidate_cards: List[Dict[str, Any]],
    ) -> str:
        """Build structured context for LLM evaluation.

        Includes ALL utterances for the current theme/section so GPT can judge
        cumulative sufficiency (not just the latest sentence in isolation).
        Capped at ~2000 chars to stay within reasonable prompt size.
        """
        # Get all utterances for this session in the current section/theme
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
        session_id: str,
        model_override: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Batch judge all cards in a single GPT call.

        Phase 3: Supports model_override parameter. When doing provisional (live) evaluation,
        pass model_override="gpt-5.4-mini". Final evaluation uses gpt-5.4-mini (default).
        """
        import json
        from app.services.openai_service import openai_service
        from app.db.session import SessionLocal
        from app.services.prompt_registry_service import prompt_registry_service

        # Phase 3: Use nano for provisional (live) evaluation, mini for final
        model = model_override or "gpt-5.4-mini"

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

            # Include current coverage progress so model knows what's already covered
            state = card_data.get('state')
            existing_evidence = getattr(state, 'evidence', None) or {} if state else {}
            already_covered = existing_evidence.get('coveredElementIds', []) or []
            current_confidence = float(state.confidence) if state and state.confidence else 0.0
            current_status = state.status if state else 'pending'

            cards_description.append(
                "\n".join([
                    f"{i}: focus=\"{card.focus_text or card.question_text}\"",
                    f"question=\"{card.question_text}\"",
                    f"required_elements={element_lines}",
                    f"expected_keywords={expected_keywords}",
                    f"semantic_anchors={semantic_anchors}",
                    f"current_status=\"{current_status}\" confidence={current_confidence:.2f} already_covered={already_covered}",
                ])
            )

        cards_list = "\n".join(cards_description)

        # Fallback prompt (used when registry is unavailable)
        system_prompt = (
            "你是 BRD 訪談評估系統。判斷對話內容是否充分回應了每個提問重點。\n\n"
            "【重要】輸入來自即時語音辨識，可能有錯字、漏字、斷句不完整。請根據語意而非字面判斷。\n\n"
            "判斷規則：\n"
            "1. 如果這段話只是在「提問」（疑問句、請求對方回答），不算覆蓋內容。confidence < 0.2，covered_element_ids 應為空。\n"
            "2. 如果句子明顯不完整（語意未結束、被截斷），confidence 應保守，不標記 covered_element_ids。\n"
            "3. 只有實質回答（描述具體情況、表達明確觀點、提供資訊）才算覆蓋。\n"
            "4. confidence=0 時，evidence_quote 必須為空字串。\n\n"
            "每張卡片會附帶目前的覆蓋進度（current_status、confidence、already_covered）。\n"
            "你只需要判斷「本次對話新增了哪些覆蓋」，不需要重新評估已覆蓋的 elements。\n"
            "covered_element_ids 應包含 already_covered 加上本次新覆蓋的 elements。\n"
            "missing_element_ids 只列出仍未被覆蓋的 elements。\n\n"
            "confidence 評分標準：\n"
            "分成兩個維度判斷：「是否被啟動」和「回答充分度」。\n\n"
            "【啟動判斷】某張卡片是否正在被討論：\n"
            "- 如果有人問了這張卡片對應方向的問題（即使還沒得到回答）→ 該卡片「已啟動」\n"
            "- 如果受訪者主動提到了這張卡片相關的話題 → 該卡片「已啟動」\n"
            "- 如果這句話和這張卡片完全無關 → 不啟動\n\n"
            "【充分度判斷】針對已啟動的卡片，根據到目前為止的所有對話累計判斷：\n"
            "- 0%：剛被問到，還沒有任何實質回答\n"
            "- 10-30%：有初步回應但內容很模糊（例如「對，大概是這樣」）\n"
            "- 30-60%：有具體描述但不完整，缺少細節或只涵蓋部分面向\n"
            "- 60-90%：有充分的描述，可作為 BRD 素材\n"
            "- 100%：完整回答，涵蓋所有 required elements，足以寫正式 BRD 段落\n\n"
            "回傳格式中的 confidence 欄位：\n"
            "- 未啟動的卡片：confidence = 0\n"
            "- 已啟動但無實質回答：confidence = 0.01（代表已啟動，進度為 0%）\n"
            "- 已啟動且有回答：confidence = 實際充分度（0.1~1.0）\n\n"
            "重要（嚴格遵守）：\n"
            "- 每句話通常只對應 0 或 1 張卡片。你給 >0 分的卡片數量不應超過 1 張，除非那句話確實同時回答了多個不同問題。\n"
            "- 「同一場訪談的主題相關」不是給分的理由。只有被直接提問或直接回答的那張卡才給 >0。\n"
            "- 如果你不確定某張卡是否被觸及，給 0。寧可漏判也不要亂給 0.1。\n"
            "- 一張卡片一旦被啟動（之前已經得到 >0），後續句子如果和它無關，維持它原來的 confidence 即可。\n"
            "- 判斷充分度時要看整段對話累計內容，不要只看最新一句。\n\n"
            "回傳格式必須是 JSON，使用 \"evaluations\" 作為唯一的 top-level key：\n"
            "{\"evaluations\": [{\"confidence\": 0.5, \"is_covered\": false, \"covered_element_ids\": [\"element_0\"], \"missing_element_ids\": [\"element_1\"], \"reason\": \"...\", \"suggested_followup\": \"...\", \"evidence_quote\": \"本次對話中的原文片段\"}]}\n"
            "evaluations 陣列的長度必須等於提問重點卡片的數量，順序一一對應。\n"
            "沒有 evidence_quote 不可標 is_covered=true。\n"
            "confidence=0 時 evidence_quote 必須為空字串。\n"
            "若本次對話完全沒有新增覆蓋，confidence 應維持或接近卡片的原有 confidence。\n"
            "suggested_followup 規則：\n"
            "- confidence < 0.7 時，必須產生追問建議（用繁體中文、口語化、可直接問出口的一句話）。\n"
            "- confidence >= 0.7 且 is_covered=true 時，回傳空字串。\n"
            "- 追問必須針對「還沒回答到的部分」，絕對不要重複問已經回答過的問題。\n"
            "- 先看 reason 裡已覆蓋了什麼，再看 missing_element_ids 裡缺什麼，追問缺的那個。\n"
            "- 例如：如果受訪者已經說了「最花時間的是資料收集」，不要再問「最花時間的是哪一段」，\n"
            "  而應該問「資料收集具體是卡在哪個步驟？」或「除了資料收集，還有沒有其他瓶頸？」"
        )
        user_prompt = (
            f"到目前為止的對話內容：\n{context[:2000]}\n\n"
            f"提問重點卡片（共 {len(candidate_cards)} 張）：\n{cards_list}\n\n"
            f"請為每張卡片評分，回傳 {len(candidate_cards)} 個結果。\n"
            f"suggested_followup 必須問「對話中還沒提到的部分」，不要重複對話中已經回答過的內容。\n"
            f"只輸出 JSON。"
        )

        # Try to load from registry
        db = SessionLocal()
        try:
            rendered = prompt_registry_service.render_prompt(
                db,
                "answer_sufficiency_batch",
                {
                    "context": context[:2000],
                    "candidate_cards": cards_list,
                    "card_count": str(len(candidate_cards)),
                }
            )
            if rendered and "system_prompt" in rendered:
                system_prompt = rendered["system_prompt"]
            if rendered and "user_prompt" in rendered:
                user_prompt = rendered["user_prompt"]
        except Exception as e:
            logger.debug(f"Failed to load answer_sufficiency_batch prompt from registry: {e}")
        finally:
            db.close()

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
                    # Phase 3: Extract evidence_quote from response
                    judgments.append({
                        "confidence": item.get("confidence", 0.0),
                        "is_covered": item.get("is_covered", item.get("covered", False)),
                        "covered_element_ids": item.get("covered_element_ids", []) or [],
                        "missing_element_ids": item.get("missing_element_ids", []) or [],
                        "reason": item.get("reason", ""),
                        "suggested_followup": item.get("suggested_followup", "") or "",
                        "evidence_quote": item.get("evidence_quote", "") or "",
                    })
                else:
                    judgments.append({
                        "confidence": 0.0,
                        "is_covered": False,
                        "suggested_followup": "",
                        "evidence_quote": "",
                    })

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
        # Confidence logic:
        # - pending: don't update
        # - listening: keep at 0 (activated but no progress shown)
        # - probably_sufficient/sufficient: accumulate upward
        if new_status == 'pending':
            new_confidence = current_confidence
        elif new_status == 'listening':
            new_confidence = 0.0
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

        # No state change — return None but evaluation is still recorded
        if new_status == old_status and new_confidence <= current_confidence:
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
        covered = judgment.get('covered_element_ids', [])

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
        elif is_covered and has_evidence:
            # >= 0.7 with evidence + is_covered = sufficient (complete)
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

            # Determine state
            if is_covered or ai_confidence >= 0.85:
                state = "sufficient"
            elif ai_confidence >= 0.62:
                state = "probably_sufficient"
            elif ai_confidence >= 0.3:
                state = "listening"
            else:
                state = "pending"

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
