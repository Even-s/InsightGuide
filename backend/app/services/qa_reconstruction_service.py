"""Q/A Reconstruction Service - Phase 4

Reconstructs the question-answer structure from finalized diarized transcripts.

This service runs after diarization completes and performs:
1. Speaker role assignment (heuristic: who asks more questions = interviewer)
2. Question detection (from interviewer utterances)
3. Question type classification (main_question | follow_up | clarification)
4. Question-to-card matching (keyword overlap with card focus/question text)
5. Answer span extraction (interviewee utterances between questions)
6. Answer summarization (using gpt-5.4-mini)
"""

import logging
import uuid
from collections import Counter
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.final_utterance import FinalUtterance
from app.models.question_answer import QuestionAnswer
from app.models.question_card import QuestionCard
from app.models.question_instance import QuestionInstance

logger = logging.getLogger(__name__)


class QAReconstructionService:

    def reconstruct(self, db: Session, session_id: str, document_id: str):
        """Main entry: run full Q/A reconstruction for a finalized session.

        Args:
            db: Database session
            session_id: Interview session ID
            document_id: Document ID (for loading question cards)
        """
        utterances = (
            db.query(FinalUtterance)
            .filter(FinalUtterance.session_id == session_id)
            .order_by(FinalUtterance.sequence_index)
            .all()
        )

        if not utterances:
            logger.warning(f"No final utterances for session {session_id}")
            return

        logger.info(
            f"Starting Q/A reconstruction for session {session_id} with {len(utterances)} utterances"
        )

        # Step 1: Assign speaker roles
        self._assign_speaker_roles(db, utterances)

        # Step 2: Detect questions
        questions = self._detect_questions(utterances)
        logger.info(f"Detected {len(questions)} questions from interviewer")

        # Step 3: Load cards for matching
        cards = db.query(QuestionCard).filter(QuestionCard.document_id == document_id).all()

        # Step 4: Extract answer spans and create records
        self._build_qa_records(db, session_id, utterances, questions, cards)

        db.commit()
        logger.info(
            f"Q/A reconstruction complete for session {session_id}: {len(questions)} questions processed"
        )

    def _assign_speaker_roles(self, db: Session, utterances: List[FinalUtterance]):
        """Heuristic: speaker with more questions = interviewer.

        Writes to final_utterances.speaker_role field.
        """
        question_patterns = [
            "？",
            "?",
            "嗎",
            "什麼",
            "如何",
            "怎麼",
            "為什麼",
            "哪些",
            "是否",
            "能否",
            "可不可以",
            "有沒有",
        ]

        speaker_question_count = Counter()
        for utt in utterances:
            if any(p in utt.transcript for p in question_patterns):
                speaker_question_count[utt.speaker_label] += 1

        if not speaker_question_count:
            # Fallback: first speaker is interviewer
            speakers = list(dict.fromkeys(u.speaker_label for u in utterances))
            interviewer = speakers[0] if speakers else None
            logger.warning(
                f"No questions detected, defaulting to first speaker as interviewer: {interviewer}"
            )
        else:
            interviewer = speaker_question_count.most_common(1)[0][0]
            logger.info(
                f"Assigned interviewer role to {interviewer} ({speaker_question_count[interviewer]} questions)"
            )

        for utt in utterances:
            if utt.speaker_label == interviewer:
                utt.speaker_role = "interviewer"
            else:
                utt.speaker_role = "interviewee"

        db.flush()

    def _detect_questions(self, utterances: List[FinalUtterance]) -> List[Dict]:
        """Find questions from interviewer utterances.

        Returns:
            List of dicts with keys: index, utterance, type, text
        """
        question_patterns = [
            "？",
            "?",
            "嗎",
            "什麼",
            "如何",
            "怎麼",
            "為什麼",
            "哪些",
            "是否",
            "能否",
            "可不可以",
            "有沒有",
        ]
        request_patterns = ["請", "描述", "說明", "舉例", "分享", "告訴", "談談", "解釋"]

        questions = []
        for i, utt in enumerate(utterances):
            if utt.speaker_role != "interviewer":
                continue

            is_question = any(p in utt.transcript for p in question_patterns)
            is_request = any(p in utt.transcript for p in request_patterns)

            if is_question or is_request:
                # Determine type: follow_up if close to previous question, otherwise main_question
                if questions and (i - questions[-1]["index"]) <= 2:
                    q_type = "follow_up"
                else:
                    q_type = "main_question"

                questions.append(
                    {
                        "index": i,
                        "utterance": utt,
                        "type": q_type,
                        "text": utt.transcript,
                    }
                )

        return questions

    def _match_question_to_card(
        self, question_text: str, cards: List[QuestionCard]
    ) -> Optional[str]:
        """Match a question to a card by keyword overlap.

        Args:
            question_text: The question text to match
            cards: List of question cards

        Returns:
            Card ID if a good match is found, None otherwise
        """
        if not cards:
            return None

        q_lower = question_text.lower()
        best_card = None
        best_score = 0

        for card in cards:
            score = 0
            # Focus text gets higher weight
            if card.focus_text:
                for word in card.focus_text.lower().split():
                    if len(word) > 2 and word in q_lower:
                        score += 2

            # Question text gets lower weight
            if card.question_text:
                for word in card.question_text.lower().split():
                    if len(word) > 2 and word in q_lower:
                        score += 1

            if score > best_score:
                best_score = score
                best_card = card

        # Require at least some overlap to match
        return best_card.id if best_card and best_score >= 2 else None

    def _build_qa_records(
        self,
        db: Session,
        session_id: str,
        utterances: List[FinalUtterance],
        questions: List[Dict],
        cards: List[QuestionCard],
    ):
        """Create QuestionInstance and QuestionAnswer records.

        For each question:
        1. Match to card (if possible)
        2. Extract answer span (interviewee utterances until next question)
        3. Create QuestionInstance and QuestionAnswer records
        """
        for q_idx, question in enumerate(questions):
            q_utt = question["utterance"]

            # Find answer span: interviewee utterances until next main_question
            next_q_index = None
            if q_idx + 1 < len(questions):
                next_q_index = questions[q_idx + 1]["index"]

            answer_utts = []
            for utt in utterances[question["index"] + 1 : next_q_index]:
                if utt.speaker_role == "interviewee":
                    answer_utts.append(utt)

            # Match to card
            card_id = self._match_question_to_card(question["text"], cards)

            # Create QuestionInstance
            qi = QuestionInstance(
                id=f"qi_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                card_id=card_id,
                theme_id=q_utt.theme_id,
                interviewer_utterance_id=q_utt.id,
                asked_text=question["text"],
                normalized_question=question["text"],
                question_type=question["type"],
                started_at=q_utt.started_at,
                ended_at=q_utt.ended_at,
                sequence_index=q_idx,
            )
            db.add(qi)

            # Create QuestionAnswer
            answer_text = "\n".join(u.transcript for u in answer_utts) if answer_utts else None
            evidence_quotes = [
                {"utterance_id": u.id, "quote": u.transcript[:200]} for u in answer_utts[:5]
            ]

            # Determine answer status
            answer_status = "answered" if answer_utts else "not_answered"
            if answer_text and len(answer_text) < 20:
                answer_status = "partially_answered"

            qa = QuestionAnswer(
                id=f"qa_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                question_instance_id=qi.id,
                answer_text=answer_text,
                answer_summary=None,  # Will be filled by summarization
                answer_utterance_ids=[u.id for u in answer_utts],
                evidence_quotes=evidence_quotes,
                answer_status=answer_status,
                confidence=0.7 if answer_utts else 0.0,
            )
            db.add(qa)

        db.flush()

        # Batch summarize answers
        self._summarize_answers(db, session_id)

    def _summarize_answers(self, db: Session, session_id: str):
        """Use gpt-5.4-mini to generate answer summaries.

        Loads all answers for the session and generates summaries in batch.
        """
        from app.services.openai_service import openai_service

        answers = (
            db.query(QuestionAnswer)
            .filter(
                QuestionAnswer.session_id == session_id,
                QuestionAnswer.answer_text.isnot(None),
            )
            .all()
        )

        if not answers:
            logger.info(f"No answers to summarize for session {session_id}")
            return

        logger.info(f"Summarizing {len(answers)} answers for session {session_id}")

        for answer in answers:
            question = (
                db.query(QuestionInstance)
                .filter(QuestionInstance.id == answer.question_instance_id)
                .first()
            )

            if not question or not answer.answer_text:
                continue

            try:
                response = openai_service.client.chat.completions.create(
                    model="gpt-5.4-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "你是訪談摘要助手。用一到兩句話摘要受訪者的回答重點。"
                                "只輸出摘要，不要其他文字。使用繁體中文。"
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"問題：{question.asked_text}\n\n受訪者回答：\n{answer.answer_text[:1500]}",
                        },
                    ],
                    temperature=0,
                    max_completion_tokens=200,
                )
                answer.answer_summary = response.choices[0].message.content.strip()
                logger.debug(f"Summarized answer {answer.id}: {answer.answer_summary[:100]}")
            except Exception as e:
                logger.error(f"Failed to summarize answer {answer.id}: {e}")
                # Fallback: use truncated answer text
                answer.answer_summary = answer.answer_text[:200] if answer.answer_text else None

        db.flush()


qa_reconstruction_service = QAReconstructionService()
