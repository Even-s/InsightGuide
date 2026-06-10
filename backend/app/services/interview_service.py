"""Interview session management service."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, and_
from fastapi import HTTPException, status

from app.models.interview_session import InterviewSession, InterviewCardState
from app.models.utterance import Utterance
from app.models.document import Document
from app.models.prep_session import PrepSession
from app.models.question_card import QuestionCard
from app.schemas.interview import (
    InterviewSessionCreate,
    InterviewSessionUpdate,
    InterviewCardStateUpdate,
    UtteranceCreate,
    InterviewSessionListResponse,
    InterviewSessionWithDocument
)
from app.services.billing_service import billing_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class InterviewService:
    """Service for interview session operations."""

    def calculate_active_duration(
        self,
        session: InterviewSession,
        end_at: Optional[datetime] = None
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

    def create_session(
        self,
        db: Session,
        user_id: str,
        session_data: InterviewSessionCreate
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
        prep_session = db.query(PrepSession).filter(
            PrepSession.id == session_data.prepSessionId
        ).first()
        if not prep_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prep session {session_data.prepSessionId} not found"
            )

        # Verify prep session belongs to user
        if prep_session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to create an interview session for this prep session"
            )

        # Verify prep session is ready
        if prep_session.status != "ready":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prep session must be ready before starting interview. Current status: {prep_session.status}"
            )

        # Verify document exists and matches
        document = db.query(Document).filter(Document.id == session_data.documentId).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {session_data.documentId} not found"
            )

        if document.id != prep_session.document_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document ID does not match prep session's document"
            )

        # Verify document is analyzed and ready
        if document.status != "analyzed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document must be analyzed before starting interview. Current status: {document.status}"
            )

        # Check for recent duplicate creation (within last 10 seconds)
        # Use SELECT FOR UPDATE to lock the prep_session row and prevent race conditions
        recent_threshold = datetime.utcnow() - timedelta(seconds=10)

        # Lock the prep_session to prevent concurrent creation
        db.query(PrepSession).filter(
            PrepSession.id == session_data.prepSessionId
        ).with_for_update().first()

        # Now check for recent sessions with the lock held
        recent_session = db.query(InterviewSession).filter(
            and_(
                InterviewSession.prep_session_id == session_data.prepSessionId,
                InterviewSession.user_id == user_id,
                InterviewSession.created_at >= recent_threshold
            )
        ).order_by(desc(InterviewSession.created_at)).first()

        if recent_session:
            logger.info(
                f"Returning existing recent session {recent_session.id} "
                f"created at {recent_session.created_at} (preventing duplicate)"
            )
            return recent_session

        # Auto-end any active sessions for this prep session
        active_sessions = db.query(InterviewSession).filter(
            InterviewSession.prep_session_id == session_data.prepSessionId,
            InterviewSession.user_id == user_id,
            InterviewSession.status.in_(['idle', 'interviewing', 'paused', 'ready'])
        ).all()

        if active_sessions:
            for old_session in active_sessions:
                ended_at = datetime.utcnow()
                self._end_current_pause(old_session, ended_at)
                old_session.status = 'ended'
                old_session.ended_at = ended_at
            db.commit()
            logger.info(f"Auto-ended {len(active_sessions)} old sessions for prep session {session_data.prepSessionId}")

        # Create session
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        session = InterviewSession(
            id=session_id,
            prep_session_id=session_data.prepSessionId,
            document_id=session_data.documentId,
            user_id=user_id,
            status="idle",
            created_at=datetime.utcnow()
        )

        db.add(session)

        # Initialize card states for all question cards in the document
        question_cards = db.query(QuestionCard).filter(
            QuestionCard.document_id == session_data.documentId
        ).all()

        for card in question_cards:
            card_state = InterviewCardState(
                id=f"cardstate_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                question_card_id=card.id,
                status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(card_state)

        db.commit()
        db.refresh(session)

        logger.info(
            f"Created interview session {session_id} for document {session_data.documentId} "
            f"with {len(question_cards)} question cards"
        )

        return session

    def get_session(self, db: Session, session_id: str) -> InterviewSession:
        """Get interview session by ID."""
        session = db.query(InterviewSession).filter(
            InterviewSession.id == session_id
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview session {session_id} not found"
            )

        return session

    def update_session(
        self,
        db: Session,
        session_id: str,
        update_data: InterviewSessionUpdate
    ) -> InterviewSession:
        """Update interview session."""
        session = self.get_session(db, session_id)
        old_section_id = session.current_section_id

        if update_data.status:
            old_status = session.status
            now = datetime.utcnow()
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
            elif update_data.status == "paused":
                if session.started_at and old_status != "paused" and not session.paused_at:
                    session.paused_at = now
            elif update_data.status == "ended" and not session.ended_at:
                self._end_current_pause(session, now)
                session.ended_at = now

        if update_data.currentSectionId is not None:
            session.current_section_id = update_data.currentSectionId

        db.commit()
        db.refresh(session)

        if (
            update_data.currentSectionId is not None
            and old_section_id
            and old_section_id != update_data.currentSectionId
        ):
            self._mark_missed_must_cards_at_risk(db, session_id, old_section_id)

        logger.info(f"Updated session {session_id}: status={session.status}")

        return session

    def _mark_missed_must_cards_at_risk(
        self,
        db: Session,
        session_id: str,
        section_id: str
    ) -> None:
        """
        Mark "must" importance question cards as "at_risk" when leaving a section.

        This helps interviewers track which critical questions were skipped.
        """
        # Get all question cards for this section
        question_cards = db.query(QuestionCard).filter(
            QuestionCard.section_id == section_id,
            QuestionCard.importance == "must"
        ).all()

        card_ids = [card.id for card in question_cards]
        if not card_ids:
            return

        # Get card states for these cards in this session
        card_states = db.query(InterviewCardState).filter(
            InterviewCardState.session_id == session_id,
            InterviewCardState.question_card_id.in_(card_ids)
        ).all()

        # Mark pending or listening cards as at_risk
        updated_count = 0
        for card_state in card_states:
            if card_state.status in ["pending", "listening"]:
                card_state.status = "at_risk"
                card_state.updated_at = datetime.utcnow()
                updated_count += 1

        if updated_count > 0:
            db.commit()
            logger.info(f"Marked {updated_count} must-ask cards as at_risk in section {section_id}")

    def update_card_state(
        self,
        db: Session,
        session_id: str,
        card_state_id: str,
        update_data: InterviewCardStateUpdate
    ) -> InterviewCardState:
        """Manually update a card state during an interview."""
        self.get_session(db, session_id)

        card_state = db.query(InterviewCardState).filter(
            InterviewCardState.id == card_state_id,
            InterviewCardState.session_id == session_id
        ).first()

        if not card_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Card state {card_state_id} not found"
            )

        old_status = card_state.status
        card_state.status = update_data.status
        card_state.confidence = update_data.confidence
        card_state.evidence_transcript = update_data.evidenceTranscript
        card_state.evidence = update_data.evidence
        card_state.updated_at = datetime.utcnow()

        # Set answered_at timestamp when status becomes sufficient
        if update_data.status in ["sufficient", "probably_sufficient"] and old_status not in ["sufficient", "probably_sufficient"]:
            card_state.answered_at = datetime.utcnow()

        db.commit()
        db.refresh(card_state)

        logger.info(f"Updated card state {card_state_id}: {old_status} -> {card_state.status}")

        return card_state

    def get_card_state(
        self,
        db: Session,
        session_id: str,
        card_state_id: str
    ) -> InterviewCardState:
        """Get a specific card state."""
        self.get_session(db, session_id)

        card_state = db.query(InterviewCardState).filter(
            InterviewCardState.id == card_state_id,
            InterviewCardState.session_id == session_id
        ).first()

        if not card_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Card state {card_state_id} not found"
            )

        return card_state

    def get_all_card_states(
        self,
        db: Session,
        session_id: str
    ) -> List[InterviewCardState]:
        """Get all card states for a session."""
        self.get_session(db, session_id)

        card_states = db.query(InterviewCardState).filter(
            InterviewCardState.session_id == session_id
        ).all()

        return card_states

    def create_utterance(
        self,
        db: Session,
        session_id: str,
        utterance_data: UtteranceCreate
    ) -> Utterance:
        """Create a new utterance in an interview session."""
        session = self.get_session(db, session_id)

        utterance_id = f"utt_{uuid.uuid4().hex[:12]}"
        utterance = Utterance(
            id=utterance_id,
            session_id=session_id,
            section_id=utterance_data.sectionId,
            speaker=utterance_data.speaker,
            transcript=utterance_data.transcript,
            started_at=utterance_data.startedAt,
            ended_at=utterance_data.endedAt,
            realtime_item_id=utterance_data.realtimeItemId,
            created_at=datetime.utcnow()
        )

        db.add(utterance)
        db.commit()
        db.refresh(utterance)

        logger.info(f"Created utterance {utterance_id} in session {session_id} (speaker: {utterance.speaker})")

        return utterance

    def get_utterances(
        self,
        db: Session,
        session_id: str,
        section_id: Optional[str] = None,
        speaker: Optional[str] = None,
        limit: int = 100
    ) -> List[Utterance]:
        """Get utterances for a session, optionally filtered by section and/or speaker."""
        self.get_session(db, session_id)

        query = db.query(Utterance).filter(Utterance.session_id == session_id)

        if section_id:
            query = query.filter(Utterance.section_id == section_id)

        if speaker:
            query = query.filter(Utterance.speaker == speaker)

        utterances = query.order_by(asc(Utterance.created_at)).limit(limit).all()

        return utterances

    def list_sessions(
        self,
        db: Session,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> InterviewSessionListResponse:
        """List interview sessions for a user."""
        # Query sessions with document information
        query = db.query(
            InterviewSession,
            Document.title.label('document_title')
        ).join(
            Document,
            InterviewSession.document_id == Document.id
        ).filter(
            InterviewSession.user_id == user_id
        )

        # Get total count
        total = query.count()

        # Get paginated results
        results = query.order_by(
            desc(InterviewSession.created_at)
        ).limit(limit).offset(offset).all()

        # Build response
        sessions = []
        for session, document_title in results:
            # Calculate duration
            duration = None
            if session.started_at:
                duration = self.calculate_active_duration(session)

            # Get cost
            cost_usd = billing_service.get_session_cost(db, session.id)
            ai_usage = billing_service.get_session_ai_usage(db, session.id)

            session_data = InterviewSessionWithDocument(
                id=session.id,
                prepSessionId=session.prep_session_id,
                documentId=session.document_id,
                documentTitle=document_title,
                userId=session.user_id,
                status=session.status,
                currentSectionId=session.current_section_id,
                startedAt=session.started_at,
                endedAt=session.ended_at,
                pausedAt=session.paused_at,
                pausedDurationSeconds=session.paused_duration_seconds or 0,
                createdAt=session.created_at,
                duration=duration,
                costUsd=cost_usd,
                aiUsage=ai_usage
            )
            sessions.append(session_data)

        return InterviewSessionListResponse(
            sessions=sessions,
            total=total,
            limit=limit,
            offset=offset
        )

    def delete_session(self, db: Session, session_id: str) -> None:
        """Delete an interview session and all related data."""
        session = self.get_session(db, session_id)

        # Delete all card states
        db.query(InterviewCardState).filter(
            InterviewCardState.session_id == session_id
        ).delete()

        # Delete all utterances
        db.query(Utterance).filter(
            Utterance.session_id == session_id
        ).delete()

        # Delete the session
        db.delete(session)
        db.commit()

        logger.info(f"Deleted interview session {session_id}")


# Singleton instance
interview_service = InterviewService()
