"""Report Analytics Service - Generate comprehensive session analytics."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.interview_session import InterviewSession, InterviewCardState
from app.models.utterance import Utterance
from app.models.question_card import QuestionCard
from app.models.section import Section
from app.services.interview_service import interview_service

logger = logging.getLogger(__name__)


class ReportAnalyticsService:
    """Service for generating comprehensive session analytics."""

    def generate_comprehensive_report(
        self, db: Session, session_id: str
    ) -> Dict[str, Any]:
        """
        Generate comprehensive analytics report for a presentation session.

        Args:
            db: Database session
            session_id: Presentation session ID

        Returns:
            Dictionary containing all analytics data
        """
        logger.info(f"Generating comprehensive report for session {session_id}")

        # Load session data
        session = db.query(InterviewSession).filter(
            InterviewSession.id == session_id
        ).first()

        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Generate all analytics components
        coverage_stats = self.calculate_coverage_stats(db, session_id)
        timeline = self.generate_timeline(db, session_id)
        topic_analysis = self.analyze_topic_performance(db, session_id)
        performance_metrics = self.calculate_performance_metrics(db, session)
        slide_timing = self.calculate_time_per_slide(db, session_id)
        insights = self.generate_insights(coverage_stats, topic_analysis, performance_metrics)

        report = {
            "session_id": session_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "session_info": {
                "status": session.status,
                "started_at": session.started_at.isoformat() + "Z" if session.started_at else None,
                "ended_at": session.ended_at.isoformat() + "Z" if session.ended_at else None,
                "duration_seconds": self._calculate_duration(session),
            },
            "coverage_stats": coverage_stats,
            "timeline": timeline,
            "topic_analysis": topic_analysis,
            "performance_metrics": performance_metrics,
            "slide_timing": slide_timing,
            "insights": insights,
        }

        logger.info(f"Report generated successfully for session {session_id}")
        return report

    def calculate_coverage_stats(self, db: Session, session_id: str) -> Dict[str, Any]:
        """
        Calculate overall coverage statistics.

        Returns:
            {
                "total_cards": int,
                "covered": int,
                "probably_covered": int,
                "at_risk": int,
                "skipped": int,
                "pending": int,
                "coverage_percentage": float,
                "must_coverage_percentage": float,
                "should_coverage_percentage": float
            }
        """
        logger.debug(f"Calculating coverage stats for session {session_id}")

        # Get all card states
        card_states = db.query(InterviewCardState).filter(
            InterviewCardState.session_id == session_id
        ).all()

        # Count by status
        status_counts = {
            "covered": 0,
            "probably_covered": 0,
            "at_risk": 0,
            "skipped": 0,
            "pending": 0,
        }

        for state in card_states:
            status = self._canonical_report_status(state.status)
            if status in status_counts:
                status_counts[status] += 1

        total_cards = len(card_states)
        covered_cards = status_counts["covered"] + status_counts["probably_covered"]

        # Calculate coverage by importance
        must_cards = []
        should_cards = []

        for state in card_states:
            card = state.question_card
            if card.importance == "must":
                must_cards.append(state)
            elif card.importance == "should":
                should_cards.append(state)

        must_covered = sum(
            1 for s in must_cards
            if self._is_acceptably_covered(s.status)
        )
        should_covered = sum(
            1 for s in should_cards
            if self._is_acceptably_covered(s.status)
        )

        stats = {
            "total_cards": total_cards,
            "covered": status_counts["covered"],
            "probably_covered": status_counts["probably_covered"],
            "at_risk": status_counts["at_risk"],
            "skipped": status_counts["skipped"],
            "pending": status_counts["pending"],
            "coverage_percentage": round((covered_cards / total_cards * 100) if total_cards > 0 else 0, 2),
            "must_cards": len(must_cards),
            "must_covered": must_covered,
            "must_coverage_percentage": round((must_covered / len(must_cards) * 100) if len(must_cards) > 0 else 0, 2),
            "should_cards": len(should_cards),
            "should_covered": should_covered,
            "should_coverage_percentage": round((should_covered / len(should_cards) * 100) if len(should_cards) > 0 else 0, 2),
        }

        logger.debug(f"Coverage stats: {stats}")
        return stats

    def generate_timeline(self, db: Session, session_id: str) -> List[Dict[str, Any]]:
        """
        Generate chronological timeline of session events.

        Returns list of events sorted by timestamp.
        """
        logger.debug(f"Generating timeline for session {session_id}")

        timeline = []

        # Get session start/end
        session = db.query(InterviewSession).filter(
            InterviewSession.id == session_id
        ).first()

        if session.started_at:
            timeline.append({
                "timestamp": session.started_at.isoformat() + "Z",
                "type": "session_start",
                "description": "Presentation started",
            })

        # Get all utterances
        utterances = db.query(Utterance).filter(
            Utterance.session_id == session_id
        ).order_by(Utterance.created_at).all()

        for utterance in utterances:
            timeline.append({
                "timestamp": utterance.created_at.isoformat() + "Z",
                "type": "utterance",
                "description": f"Spoke: {utterance.transcript[:50]}...",
                "transcript": utterance.transcript,
                "slide_id": utterance.section_id,
            })

        # Get card state changes
        card_states = db.query(InterviewCardState).filter(
            InterviewCardState.session_id == session_id,
            InterviewCardState.answered_at.isnot(None)
        ).order_by(InterviewCardState.answered_at).all()

        for state in card_states:
            timeline.append({
                "timestamp": state.answered_at.isoformat() + "Z",
                "type": "card_covered",
                "description": f"Topic covered: {state.question_card.question_text}",
                "card_id": state.question_card_id,
                "card_title": state.question_card.question_text,
                "status": state.status,
                "confidence": float(state.confidence) if state.confidence else None,
            })

        if session.ended_at:
            timeline.append({
                "timestamp": session.ended_at.isoformat() + "Z",
                "type": "session_end",
                "description": "Presentation ended",
            })

        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"])

        logger.debug(f"Generated {len(timeline)} timeline events")
        return timeline

    def analyze_topic_performance(
        self, db: Session, session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Analyze performance for each topic card.

        Returns list of topic analyses with detailed metrics.
        """
        logger.debug(f"Analyzing topic performance for session {session_id}")

        card_states = db.query(InterviewCardState).filter(
            InterviewCardState.session_id == session_id
        ).all()

        topic_analysis = []

        for state in card_states:
            card = state.question_card

            analysis = {
                "card_id": state.question_card_id,
                "title": card.question_text,
                "description": card.question_text,
                "importance": card.importance,
                "status": state.status,
                "confidence": float(state.confidence) if state.confidence else 0,
                "slide_page": card.section_number,
                "estimated_seconds": card.estimated_seconds,
                "covered_at": state.answered_at.isoformat() + "Z" if state.answered_at else None,
                "evidence_transcript": state.evidence_transcript,
                "success": self._is_acceptably_covered(state.status),
            }

            topic_analysis.append(analysis)

        # Sort by slide page number
        topic_analysis.sort(key=lambda x: x["slide_page"])

        logger.debug(f"Analyzed {len(topic_analysis)} topics")
        return topic_analysis

    def calculate_performance_metrics(
        self, db: Session, session: InterviewSession
    ) -> Dict[str, Any]:
        """
        Calculate overall performance metrics.

        Returns:
            {
                "total_duration_seconds": int,
                "total_utterances": int,
                "total_characters": int,
                "characters_per_minute": float,
                "avg_utterance_characters": float,
                "slides_visited": int
            }
        """
        logger.debug(f"Calculating performance metrics for session {session.id}")

        duration = self._calculate_duration(session)

        # Get utterances
        utterances = db.query(Utterance).filter(
            Utterance.session_id == session.id
        ).all()

        total_characters = sum(self._count_chinese_characters(u.transcript) for u in utterances)
        avg_utterance_characters = (
            total_characters / len(utterances) if len(utterances) > 0 else 0
        )

        # Calculate Chinese characters per minute.
        characters_per_minute = 0
        if duration and duration > 0:
            duration_minutes = duration / 60
            characters_per_minute = (
                total_characters / duration_minutes if duration_minutes > 0 else 0
            )

        # Count unique sections visited. The report keeps the legacy field name.
        slides_visited = db.query(func.count(func.distinct(Utterance.section_id))).filter(
            Utterance.session_id == session.id,
            Utterance.section_id.isnot(None)
        ).scalar() or 0

        metrics = {
            "total_duration_seconds": duration or 0,
            "total_utterances": len(utterances),
            "total_characters": total_characters,
            "characters_per_minute": round(characters_per_minute, 2),
            "avg_utterance_characters": round(avg_utterance_characters, 2),
            # Compatibility for older consumers. These now mirror Chinese character metrics.
            "total_words": total_characters,
            "words_per_minute": round(characters_per_minute, 2),
            "avg_utterance_length": round(avg_utterance_characters, 2),
            "slides_visited": slides_visited,
        }

        logger.debug(f"Performance metrics: {metrics}")
        return metrics

    def calculate_time_per_slide(
        self, db: Session, session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Calculate time spent on each slide.

        Returns list of slide timing data.
        """
        logger.debug(f"Calculating slide timing for session {session_id}")

        utterances = db.query(Utterance).filter(
            Utterance.session_id == session_id,
            Utterance.section_id.isnot(None)
        ).order_by(Utterance.created_at).all()

        slide_times = {}

        for i, utterance in enumerate(utterances):
            slide_id = utterance.section_id
            if slide_id not in slide_times:
                slide_times[slide_id] = {
                    "first_utterance": utterance.created_at,
                    "last_utterance": utterance.created_at,
                    "utterance_count": 0,
                }

            slide_times[slide_id]["last_utterance"] = utterance.created_at
            slide_times[slide_id]["utterance_count"] += 1

        # Calculate duration for each slide
        slide_timing = []

        for slide_id, times in slide_times.items():
            duration = (
                times["last_utterance"] - times["first_utterance"]
            ).total_seconds()

            # Load slide info
            slide = db.query(Section).filter(Section.id == slide_id).first()

            slide_timing.append({
                "slide_id": slide_id,
                "slide_page": slide.page_number if slide else None,
                "slide_title": slide.title if slide else None,
                "duration_seconds": round(duration, 2),
                "utterance_count": times["utterance_count"],
                "first_utterance": times["first_utterance"].isoformat() + "Z",
                "last_utterance": times["last_utterance"].isoformat() + "Z",
            })

        # Sort by page number
        slide_timing.sort(key=lambda x: x["slide_page"] or 0)

        logger.debug(f"Calculated timing for {len(slide_timing)} slides")
        return slide_timing

    def generate_insights(
        self,
        coverage_stats: Dict[str, Any],
        topic_analysis: List[Dict[str, Any]],
        performance_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate AI-powered insights and recommendations.

        Returns insights dictionary with strengths and recommendations.
        """
        logger.debug("Generating insights")

        insights = {
            "strengths": [],
            "areas_for_improvement": [],
            "recommendations": [],
        }

        # Analyze coverage
        coverage_pct = coverage_stats["coverage_percentage"]
        if coverage_pct >= 90:
            insights["strengths"].append({
                "category": "coverage",
                "description": f"Excellent coverage at {coverage_pct}% - all key topics addressed",
            })
        elif coverage_pct >= 70:
            insights["strengths"].append({
                "category": "coverage",
                "description": f"Good coverage at {coverage_pct}% - most topics covered",
            })
        else:
            insights["areas_for_improvement"].append({
                "category": "coverage",
                "description": f"Coverage at {coverage_pct}% - several topics not addressed",
            })
            insights["recommendations"].append({
                "category": "coverage",
                "priority": "high",
                "recommendation": "Review uncovered topics and ensure all 'must' items are included in next presentation",
            })

        # Analyze must-have topics
        must_coverage = coverage_stats["must_coverage_percentage"]
        if must_coverage < 100:
            insights["areas_for_improvement"].append({
                "category": "critical_topics",
                "description": f"Only {must_coverage}% of critical 'must' topics were covered",
            })
            insights["recommendations"].append({
                "category": "critical_topics",
                "priority": "high",
                "recommendation": "Focus on covering all 'must' topics - they are essential to your presentation",
            })
        else:
            insights["strengths"].append({
                "category": "critical_topics",
                "description": "All critical 'must' topics were successfully covered",
            })

        # Analyze speaking pace by Chinese characters per minute.
        cpm = performance_metrics["characters_per_minute"]
        if 220 <= cpm <= 320:
            insights["strengths"].append({
                "category": "pacing",
                "description": f"Good speaking pace at {cpm} Chinese chars/min - clear and understandable",
            })
        elif cpm > 320:
            insights["areas_for_improvement"].append({
                "category": "pacing",
                "description": f"Speaking pace at {cpm} Chinese chars/min is fast - audience may struggle to follow",
            })
            insights["recommendations"].append({
                "category": "pacing",
                "priority": "medium",
                "recommendation": "Try slowing down to 220-320 Chinese chars/min for better audience comprehension",
            })
        elif cpm < 220 and cpm > 0:
            insights["areas_for_improvement"].append({
                "category": "pacing",
                "description": f"Speaking pace at {cpm} Chinese chars/min is slow - may lose audience engagement",
            })
            insights["recommendations"].append({
                "category": "pacing",
                "priority": "low",
                "recommendation": "Consider picking up the pace slightly to maintain audience interest",
            })

        # Analyze at-risk topics
        at_risk_count = coverage_stats["at_risk"]
        if at_risk_count > 0:
            insights["areas_for_improvement"].append({
                "category": "timing",
                "description": f"{at_risk_count} important topics were flagged as 'at risk' due to timing",
            })
            insights["recommendations"].append({
                "category": "timing",
                "priority": "medium",
                "recommendation": "Practice time management to ensure all important topics get adequate coverage",
            })

        logger.debug(f"Generated {len(insights['strengths'])} strengths and {len(insights['recommendations'])} recommendations")
        return insights

    def _count_chinese_characters(self, text: str | None) -> int:
        """Count CJK Chinese characters, excluding punctuation, spaces, numbers, and Latin text."""
        if not text:
            return 0

        return sum(
            1
            for char in text
            if (
                "\u3400" <= char <= "\u4dbf"
                or "\u4e00" <= char <= "\u9fff"
                or "\uf900" <= char <= "\ufaff"
            )
        )

    def _calculate_duration(self, session: InterviewSession) -> Optional[int]:
        """Calculate session duration in seconds."""
        return interview_service.calculate_active_duration(session, session.ended_at)

    @staticmethod
    def _canonical_report_status(status: str) -> str:
        """Keep report API fields stable while accepting the BRD status vocabulary."""
        if status == "sufficient":
            return "covered"
        if status == "probably_sufficient":
            return "probably_covered"
        if status in {"covered", "probably_covered", "at_risk", "skipped"}:
            return status
        return "pending"

    @classmethod
    def _is_acceptably_covered(cls, status: str) -> bool:
        return cls._canonical_report_status(status) in {"covered", "probably_covered"}


# Singleton instance
report_analytics_service = ReportAnalyticsService()
