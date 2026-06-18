"""Utterance Alignment Service - Phase 5

Aligns live_utterances (Realtime API transcripts) to final_utterances (diarized transcripts)
using time overlap and text similarity.
"""

import logging
import uuid
from datetime import timedelta
from typing import List
from sqlalchemy.orm import Session

from app.models.live_utterance import LiveUtterance
from app.models.final_utterance import FinalUtterance
from app.models.utterance_alignment import UtteranceAlignment

logger = logging.getLogger(__name__)


class AlignmentService:
    """Service for aligning live and final utterances."""

    def align(self, db: Session, session_id: str, transcript_revision_id: str):
        """Align live_utterances to final_utterances by time overlap and text similarity.

        Args:
            db: Database session
            session_id: Interview session ID
            transcript_revision_id: Transcript revision ID from diarization
        """
        # Load all non-partial live utterances
        lives = db.query(LiveUtterance).filter(
            LiveUtterance.session_id == session_id,
            LiveUtterance.is_partial == False,
        ).order_by(LiveUtterance.created_at).all()

        # Load all final utterances for this revision
        finals = db.query(FinalUtterance).filter(
            FinalUtterance.session_id == session_id,
            FinalUtterance.transcript_revision_id == transcript_revision_id,
        ).order_by(FinalUtterance.sequence_index).all()

        if not lives or not finals:
            logger.info(f"Alignment skipped for session {session_id}: lives={len(lives)}, finals={len(finals)}")
            return

        records = []
        for live in lives:
            # Determine live utterance time range
            live_start = live.started_at or live.created_at
            live_end = live.ended_at or (live_start + timedelta(seconds=3))

            best_final = None
            best_overlap = 0.0

            # Find the final utterance with the best time overlap
            for final in finals:
                if not final.started_at:
                    continue
                final_start = final.started_at
                final_end = final.ended_at or (final_start + timedelta(seconds=3))

                # Compute overlap duration in seconds
                overlap_start = max(live_start, final_start)
                overlap_end = min(live_end, final_end)
                overlap = max(0, (overlap_end - overlap_start).total_seconds())

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_final = final

            # Compute text similarity (simple character overlap ratio)
            text_sim = 0.0
            if best_final:
                text_sim = self._text_similarity(live.transcript, best_final.transcript)

            # Combined confidence: 60% time overlap, 40% text similarity
            time_score = min(best_overlap / 3.0, 1.0) if best_overlap > 0 else 0.0
            confidence = (time_score * 0.6 + text_sim * 0.4) if best_final else 0.0

            # Only create alignment if confidence is above threshold (0.2)
            records.append(UtteranceAlignment(
                id=f"ua_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                live_utterance_id=live.id,
                final_utterance_id=best_final.id if best_final and confidence > 0.2 else None,
                transcript_revision_id=transcript_revision_id,
                time_overlap_score=time_score,
                text_similarity_score=text_sim,
                alignment_confidence=confidence,
            ))

        # Bulk insert alignment records
        db.bulk_save_objects(records)
        db.flush()

        matched_count = sum(1 for r in records if r.final_utterance_id)
        logger.info(
            f"Alignment complete for session {session_id}: "
            f"{len(records)} records, {matched_count} matched ({matched_count * 100 / len(records):.1f}%)"
        )

    def _text_similarity(self, a: str, b: str) -> float:
        """Simple character-level overlap ratio.

        Uses set intersection of characters (ignoring spaces) to compute similarity.
        """
        if not a or not b:
            return 0.0
        a_set = set(a.replace(" ", ""))
        b_set = set(b.replace(" ", ""))
        if not a_set or not b_set:
            return 0.0
        intersection = a_set & b_set
        return len(intersection) / max(len(a_set), len(b_set))


alignment_service = AlignmentService()
