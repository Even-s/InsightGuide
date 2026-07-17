"""Interview session management service."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, asc, desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.card_coverage_evaluation import CardCoverageEvaluation
from app.models.card_criterion_evidence import CardCriterionEvidence
from app.models.document import Document
from app.models.interview_round import InterviewRound
from app.models.interview_session import InterviewCardState, InterviewSession
from app.models.live_utterance import LiveUtterance
from app.models.prep_session import PrepSession
from app.models.question_card import QuestionCard
from app.schemas.interview import (
    InterviewCardStateUpdate,
    InterviewSessionCreate,
    InterviewSessionListResponse,
    InterviewSessionUpdate,
    InterviewSessionWithDocument,
    UtteranceCreate,
)
from app.services.billing_service import billing_service

logger = logging.getLogger(__name__)


class InterviewService:
    """Service for interview session operations."""

    @staticmethod
    def clear_completed_card_routing(
        session: InterviewSession,
        card_id: str,
    ) -> bool:
        """Release routing pointers once their card has been completed.

        Completed cards are terminal and must not remain the destination for
        later transcript segments.  Return whether any pointer was cleared so
        callers can persist the session in their existing transaction.
        """
        if session.active_card_id != card_id:
            return False

        session.active_card_id = None
        session.active_card_source = "completed"
        session.active_card_confirmed_at = None
        session.pending_answer_buffer = None
        return True

    @staticmethod
    def _build_card_state(
        session_id: str,
        card_id: str,
    ) -> InterviewCardState:
        """Create a fresh per-session card state.

        Continued interviews no longer duplicate prior session progress or
        evidence. Cumulative progress lives on InterviewRoundAggregate; a new
        session records only the delta from that visit. Role applicability is
        recalculated for each session by RoleFilterService instead of being
        copied from the source session.
        """
        return InterviewCardState(
            id=f"cardstate_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            question_card_id=card_id,
            status="pending",
            confidence=None,
            activation_score=0,
            completion_score=0,
            completion_source=None,
            manual_note=None,
            answered_at=None,
            evidence_transcript=None,
            evidence=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def calculate_active_duration(
        self, session: InterviewSession, end_at: Optional[datetime] = None
    ) -> Optional[int]:
        """Calculate interview duration excluding paused time."""
        if not session.started_at:
            return None

        effective_end = end_at or session.ended_at or datetime.utcnow()
        paused_seconds = session.paused_duration_seconds or 0

        if session.paused_at:
            pause_end = min(effective_end, datetime.utcnow())
            if pause_end > session.paused_at:
                paused_seconds += int((pause_end - session.paused_at).total_seconds())

        elapsed = int((effective_end - session.started_at).total_seconds())
        return max(0, elapsed - paused_seconds)

    def _end_current_pause(self, session: InterviewSession, ended_at: datetime) -> None:
        """Fold the current paused interval into paused_duration_seconds."""
        if not session.paused_at:
            return

        if ended_at > session.paused_at:
            session.paused_duration_seconds = (session.paused_duration_seconds or 0) + int(
                (ended_at - session.paused_at).total_seconds()
            )
        session.paused_at = None

    def _reset_card_progress_for_new_round(
        self,
        db: Session,
        session: InterviewSession,
    ) -> None:
        """Clear provisional card progress before the first interview start.

        Role-filtered states are preserved, while every interviewable card is
        returned to a clean pending state. The related evaluation ledgers must
        be cleared as well; otherwise old criterion evidence would immediately
        rebuild stale completion on the next answer.
        """
        preserved_statuses = {
            "not_applicable_for_role",
            "needs_different_stakeholder",
            "disabled",
        }
        card_states = (
            db.query(InterviewCardState).filter(InterviewCardState.session_id == session.id).all()
        )

        for card_state in card_states:
            if card_state.status not in preserved_statuses:
                card_state.status = "pending"
            card_state.confidence = None
            card_state.activation_score = 0
            card_state.completion_score = 0
            card_state.completion_source = None
            card_state.manual_note = None
            card_state.answered_at = None
            card_state.evidence_transcript = None
            card_state.evidence = None
            card_state.updated_at = datetime.utcnow()

        db.query(CardCoverageEvaluation).filter(
            CardCoverageEvaluation.session_id == session.id
        ).delete(synchronize_session=False)
        db.query(CardCriterionEvidence).filter(
            CardCriterionEvidence.session_id == session.id
        ).delete(synchronize_session=False)

        session.active_card_id = None
        session.active_card_source = None
        session.active_card_confirmed_at = None
        session.pending_answer_buffer = None
        logger.info(
            "Reset card progress for new interview round session=%s cards=%s",
            session.id,
            len(card_states),
        )

    def create_session(
        self, db: Session, user_id: str, session_data: InterviewSessionCreate
    ) -> InterviewSession:
        """
        Create a new interview session under a prep session.

        Args:
            db: Database session
            user_id: User ID
            session_data: Session creation data (includes prepSessionId)

        Returns:
            Created interview session
        """
        # Verify prep session exists
        prep_session = (
            db.query(PrepSession).filter(PrepSession.id == session_data.prepSessionId).first()
        )
        if not prep_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prep session {session_data.prepSessionId} not found",
            )

        # Verify prep session belongs to user
        if prep_session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to create an interview session for this prep session",
            )

        # Verify prep session is ready
        if prep_session.status != "ready":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prep session must be ready before starting interview. Current status: {prep_session.status}",
            )

        # Verify document exists and matches
        document = db.query(Document).filter(Document.id == session_data.documentId).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {session_data.documentId} not found",
            )

        if document.id != prep_session.document_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document ID does not match prep session's document",
            )

        interview_round = None
        interview_round_id = (
            getattr(session_data, "interviewRoundId", None) or document.interview_round_id
        )
        if interview_round_id:
            interview_round = (
                db.query(InterviewRound).filter(InterviewRound.id == interview_round_id).first()
            )
            if not interview_round:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Interview round {interview_round_id} not found",
                )
            if interview_round.guide_document_id != document.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Interview round does not use the requested guide document",
                )

        continuation_source = None
        continuation_source_id = getattr(session_data, "continueFromSessionId", None)
        if continuation_source_id:
            continuation_source = (
                db.query(InterviewSession)
                .filter(InterviewSession.id == continuation_source_id)
                .first()
            )
            if not continuation_source:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Source interview session {continuation_source_id} not found",
                )
            if continuation_source.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to continue this interview session",
                )
            if (
                continuation_source.document_id != document.id
                or continuation_source.interview_round_id != interview_round_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Continuation source must belong to the same interview round and guide",
                )
            if continuation_source.status != "ended":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only an ended interview session can start a continuation",
                )

        if document.is_frozen and not continuation_source:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This interview guide already has a session and is frozen. "
                    "Create a new interview round instead."
                ),
            )

        # Verify document is analyzed and ready
        if document.status != "analyzed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document must be analyzed before starting interview. Current status: {document.status}",
            )

        # Check for recent duplicate creation (within last 10 seconds)
        # Use SELECT FOR UPDATE to lock the prep_session row and prevent race conditions
        recent_threshold = datetime.utcnow() - timedelta(seconds=10)

        # Lock the prep_session to prevent concurrent creation
        db.query(PrepSession).filter(
            PrepSession.id == session_data.prepSessionId
        ).with_for_update().first()

        # Now check for recent sessions with the lock held
        recent_filters = [
            InterviewSession.prep_session_id == session_data.prepSessionId,
            InterviewSession.user_id == user_id,
            InterviewSession.created_at >= recent_threshold,
        ]
        if continuation_source:
            recent_filters.extend(
                [
                    InterviewSession.id != continuation_source.id,
                    InterviewSession.continued_from_session_id == continuation_source.id,
                ]
            )
        recent_session = (
            db.query(InterviewSession)
            .filter(and_(*recent_filters))
            .order_by(desc(InterviewSession.created_at))
            .first()
        )

        if recent_session:
            logger.info(
                f"Returning existing recent session {recent_session.id} "
                f"created at {recent_session.created_at} (preventing duplicate)"
            )
            return recent_session

        # Auto-end any active sessions for this prep session
        active_sessions = (
            db.query(InterviewSession)
            .filter(
                InterviewSession.prep_session_id == session_data.prepSessionId,
                InterviewSession.user_id == user_id,
                InterviewSession.status.in_(["idle", "interviewing", "paused", "ready"]),
            )
            .all()
        )

        if active_sessions:
            for old_session in active_sessions:
                ended_at = datetime.utcnow()
                self._end_current_pause(old_session, ended_at)
                old_session.status = "ended"
                old_session.ended_at = ended_at
                if old_session.interview_round:
                    old_session.interview_round.status = "completed"
            db.commit()
            logger.info(
                f"Auto-ended {len(active_sessions)} old sessions for prep session {session_data.prepSessionId}"
            )

        # Create session
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        project_id = getattr(session_data, "projectId", None)
        stakeholder_profile_id = getattr(session_data, "stakeholderProfileId", None)
        session = InterviewSession(
            id=session_id,
            prep_session_id=session_data.prepSessionId,
            document_id=session_data.documentId,
            user_id=user_id,
            project_id=project_id,
            stakeholder_profile_id=stakeholder_profile_id,
            interview_round_id=interview_round_id,
            continued_from_session_id=(continuation_source.id if continuation_source else None),
            status="idle",
            created_at=datetime.utcnow(),
        )

        db.add(session)
        # Persist the parent row before creating per-session card rows.
        # These models are linked by scalar foreign-key IDs rather than ORM
        # relationships, so SQLAlchemy cannot otherwise guarantee insert order.
        db.flush([session])
        document.is_frozen = True
        if interview_round:
            interview_round.status = "scheduled"

        # Initialize card states for all question cards in the document
        question_cards = (
            db.query(QuestionCard).filter(QuestionCard.document_id == session_data.documentId).all()
        )

        for card in question_cards:
            card_state = self._build_card_state(session_id, card.id)
            db.add(card_state)

        db.commit()
        db.refresh(session)

        if interview_round_id:
            from app.services.interview_round_aggregate_service import (
                interview_round_aggregate_service,
            )

            interview_round_aggregate_service.invalidate(db, interview_round_id)

        # Auto-apply role filter if stakeholder is set. Continuations also
        # recalculate role applicability instead of copying source session state.
        if stakeholder_profile_id:
            try:
                from app.services.role_filter_service import role_filter_service

                result = role_filter_service.apply_role_filter_to_session(db, session_id)
                logger.info(
                    f"Role filter applied: {result.get('applicable', 0)} applicable, "
                    f"{result.get('not_applicable', 0)} not applicable"
                )
            except Exception as e:
                logger.warning(f"Role filter failed (non-fatal): {e}")

        logger.info(
            f"Created interview session {session_id} for document {session_data.documentId} "
            f"with {len(question_cards)} question cards"
            + (f" continued from {continuation_source.id}" if continuation_source else "")
        )

        return session

    def get_session(self, db: Session, session_id: str) -> InterviewSession:
        """Get interview session by ID."""
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview session {session_id} not found",
            )

        return session

    def update_session(
        self, db: Session, session_id: str, update_data: InterviewSessionUpdate
    ) -> InterviewSession:
        """Update interview session."""
        session = self.get_session(db, session_id)
        old_theme_id = session.current_theme_id

        logger.info(
            "update_session payload: status=%s, currentThemeId=%s",
            update_data.status,
            update_data.currentThemeId,
        )

        if update_data.status:
            old_status = session.status
            now = datetime.utcnow()

            if (
                update_data.status == "interviewing"
                and not session.continued_from_session_id
                and old_status
                in [
                    "idle",
                    "ready",
                    "preparing",
                ]
            ):
                self._reset_card_progress_for_new_round(db, session)

            session.status = update_data.status

            # Set timestamps based on status transitions
            if update_data.status == "interviewing":
                # Only set started_at if transitioning from idle/ready
                # Keep started_at when resuming from pause
                if old_status in ["idle", "ready", "preparing"] or not session.started_at:
                    session.started_at = now
                    session.paused_at = None
                    session.paused_duration_seconds = 0
                    session.ended_at = None
                elif old_status == "paused":
                    self._end_current_pause(session, now)
                if session.interview_round:
                    session.interview_round.status = "interviewing"
            elif update_data.status == "paused":
                if session.started_at and old_status != "paused" and not session.paused_at:
                    session.paused_at = now
            elif update_data.status == "ended" and not session.ended_at:
                self._end_current_pause(session, now)
                session.ended_at = now
                if session.interview_round:
                    session.interview_round.status = "completed"

        if update_data.currentThemeId is not None:
            session.current_theme_id = update_data.currentThemeId

        db.commit()
        db.refresh(session)

        if (
            update_data.currentThemeId is not None
            and old_theme_id
            and old_theme_id != update_data.currentThemeId
        ):
            self._mark_missed_must_cards_at_risk(db, session_id, old_theme_id)

        logger.info(f"Updated session {session_id}: status={session.status}")

        return session

    def _mark_missed_must_cards_at_risk(self, db: Session, session_id: str, theme_id: str) -> None:
        """
        Mark "must" importance question cards as "at_risk" when leaving a theme.

        This helps facilitators track which critical questions were skipped.
        """
        # Get all question cards for this interview theme
        question_cards = (
            db.query(QuestionCard)
            .filter(
                QuestionCard.interview_theme_id == theme_id,
                QuestionCard.importance == "must",
            )
            .all()
        )

        card_ids = [card.id for card in question_cards]
        if not card_ids:
            return

        # Get card states for these cards in this session
        card_states = (
            db.query(InterviewCardState)
            .filter(
                InterviewCardState.session_id == session_id,
                InterviewCardState.question_card_id.in_(card_ids),
            )
            .all()
        )

        # Mark pending or listening cards as at_risk
        updated_count = 0
        for card_state in card_states:
            if card_state.status in ["pending", "listening"]:
                card_state.status = "at_risk"
                card_state.updated_at = datetime.utcnow()
                updated_count += 1

        if updated_count > 0:
            db.commit()
            logger.info("Marked %s must-ask cards as at_risk in theme %s", updated_count, theme_id)

    def update_card_state(
        self,
        db: Session,
        session_id: str,
        card_state_id: str,
        update_data: InterviewCardStateUpdate,
    ) -> InterviewCardState:
        """Manually update a card state during an interview."""
        self.get_session(db, session_id)

        card_state = (
            db.query(InterviewCardState)
            .filter(
                InterviewCardState.id == card_state_id, InterviewCardState.session_id == session_id
            )
            .first()
        )

        if not card_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Card state {card_state_id} not found",
            )

        old_status = card_state.status
        card_state.status = update_data.status
        card_state.confidence = update_data.confidence
        card_state.evidence_transcript = update_data.evidenceTranscript
        card_state.evidence = update_data.evidence
        card_state.updated_at = datetime.utcnow()

        # Set answered_at timestamp when status becomes sufficient
        if update_data.status in ["sufficient", "probably_sufficient"] and old_status not in [
            "sufficient",
            "probably_sufficient",
        ]:
            card_state.answered_at = datetime.utcnow()

        db.commit()
        db.refresh(card_state)

        logger.info(f"Updated card state {card_state_id}: {old_status} -> {card_state.status}")

        return card_state

    def get_all_card_states(self, db: Session, session_id: str) -> List[InterviewCardState]:
        """Get all card states for a session."""
        self.get_session(db, session_id)

        card_states = (
            db.query(InterviewCardState).filter(InterviewCardState.session_id == session_id).all()
        )

        return card_states

    def get_session_cards(self, db: Session, session_id: str) -> List[InterviewCardState]:
        """Get question cards with their runtime state for a session."""
        from sqlalchemy.orm import joinedload

        self.get_session(db, session_id)

        return (
            db.query(InterviewCardState)
            .options(
                joinedload(InterviewCardState.question_card).joinedload(
                    QuestionCard.interview_theme
                )
            )
            .filter(InterviewCardState.session_id == session_id)
            .join(QuestionCard, InterviewCardState.question_card_id == QuestionCard.id)
            .order_by(
                QuestionCard.interview_theme_id,
                QuestionCard.order_index,
                QuestionCard.id,
            )
            .all()
        )

    def create_utterance(
        self, db: Session, session_id: str, utterance_data: UtteranceCreate
    ) -> LiveUtterance:
        """Create a new live utterance from Realtime API in an interview session.

        Realtime utterances are the canonical transcript used during and after
        the interview.
        """
        self.get_session(db, session_id)

        utterance_id = f"utt_{uuid.uuid4().hex[:12]}"

        # Calculate sequence index based on existing live utterances
        existing_count = (
            db.query(LiveUtterance).filter(LiveUtterance.session_id == session_id).count()
        )

        utterance = LiveUtterance(
            id=utterance_id,
            session_id=session_id,
            realtime_event_id=utterance_data.realtimeItemId,
            theme_id=utterance_data.themeId,
            asked_card_ids=utterance_data.askedCardIds or [],
            transcript=utterance_data.transcript,
            started_at=utterance_data.startedAt,
            ended_at=utterance_data.endedAt,
            sequence_index=existing_count,
            created_at=datetime.utcnow(),
        )

        db.add(utterance)
        db.commit()
        db.refresh(utterance)

        logger.info("Created live utterance %s in session %s", utterance_id, session_id)

        return utterance

    def get_utterances(
        self,
        db: Session,
        session_id: str,
        limit: int = 100,
    ) -> list:
        """Get utterances for a session.

        Realtime transcript segments are the only canonical source.
        """
        self.get_session(db, session_id)

        query = db.query(LiveUtterance).filter(LiveUtterance.session_id == session_id)
        return query.order_by(asc(LiveUtterance.sequence_index)).limit(limit).all()

    def list_sessions(
        self,
        db: Session,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        project_id: Optional[str] = None,
        document_id: Optional[str] = None,
        stakeholder_profile_id: Optional[str] = None,
    ) -> InterviewSessionListResponse:
        """List sessions with project, document, and stakeholder filters."""
        # Query sessions with document information
        query = (
            db.query(InterviewSession, Document.title.label("document_title"))
            .join(Document, InterviewSession.document_id == Document.id)
            .filter(InterviewSession.user_id == user_id)
        )

        if project_id:
            query = query.filter(InterviewSession.project_id == project_id)

        if document_id:
            query = query.filter(InterviewSession.document_id == document_id)

        if stakeholder_profile_id:
            query = query.filter(InterviewSession.stakeholder_profile_id == stakeholder_profile_id)

        # Get total count
        total = query.count()

        # Get paginated results
        results = (
            query.order_by(desc(InterviewSession.created_at)).limit(limit).offset(offset).all()
        )

        usage_by_session_id = billing_service.summarize_sessions(
            db,
            [session.id for session, _ in results],
        )

        # Build response
        sessions = []
        for session, document_title in results:
            # Calculate duration
            duration = None
            if session.started_at:
                duration = self.calculate_active_duration(session)

            ai_usage = usage_by_session_id.get(session.id, billing_service.empty_summary())

            session_data = InterviewSessionWithDocument(
                id=session.id,
                prepSessionId=session.prep_session_id,
                documentId=session.document_id,
                documentTitle=document_title,
                userId=session.user_id,
                projectId=session.project_id,
                stakeholderProfileId=session.stakeholder_profile_id,
                interviewRoundId=session.interview_round_id,
                continuedFromSessionId=session.continued_from_session_id,
                status=session.status,
                currentThemeId=session.current_theme_id,
                startedAt=session.started_at,
                endedAt=session.ended_at,
                pausedAt=session.paused_at,
                pausedDurationSeconds=session.paused_duration_seconds or 0,
                createdAt=session.created_at,
                duration=duration,
                costUsd=ai_usage["totalCostUsd"],
                aiUsage=ai_usage,
            )
            sessions.append(session_data)

        return InterviewSessionListResponse(
            sessions=sessions, total=total, limit=limit, offset=offset
        )

    def delete_session(self, db: Session, session_id: str) -> None:
        """Delete an interview session and all related data."""
        session = self.get_session(db, session_id)

        if session.interview_round_id:
            from app.services.interview_round_aggregate_service import (
                interview_round_aggregate_service,
            )

            interview_round_aggregate_service.invalidate(
                db, session.interview_round_id, commit=False
            )

        # Delete all card states
        db.query(InterviewCardState).filter(InterviewCardState.session_id == session_id).delete()

        # Delete the session
        db.delete(session)
        db.commit()

        logger.info(f"Deleted interview session {session_id}")


# Singleton instance
interview_service = InterviewService()
