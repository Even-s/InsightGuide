"""Session Reports API routes."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.report_analytics_service import report_analytics_service
from app.services.report_export_service import report_export_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{session_id}/report")
async def generate_session_report(
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Generate comprehensive analytics report for an interview session.

    Args:
        session_id: Interview session ID

    Returns:
        Complete analytics report with answer coverage, timeline, insights, etc.
    """
    logger.info(f"API: Generating report for session {session_id}")

    try:
        report = report_analytics_service.generate_comprehensive_report(db, session_id)
        return report
    except ValueError as e:
        logger.error(f"Session not found: {session_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate report"
        )


@router.get("/{session_id}/report/coverage")
async def get_coverage_stats(
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get answer coverage statistics for an interview session.

    Args:
        session_id: Interview session ID

    Returns:
        Answer coverage statistics
    """
    logger.info(f"API: Getting coverage stats for session {session_id}")

    try:
        stats = report_analytics_service.calculate_coverage_stats(db, session_id)
        return stats
    except Exception as e:
        logger.error(f"Error getting coverage stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get coverage statistics",
        )


@router.get("/{session_id}/report/timeline")
async def get_session_timeline(
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get chronological timeline of interview session events.

    Args:
        session_id: Interview session ID

    Returns:
        Timeline of events
    """
    logger.info(f"API: Getting timeline for session {session_id}")

    try:
        timeline = report_analytics_service.generate_timeline(db, session_id)
        return {"session_id": session_id, "events": timeline}
    except Exception as e:
        logger.error(f"Error getting timeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get timeline"
        )


@router.get("/{session_id}/report/questions")
async def get_question_analysis(
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get per-question answer analysis.

    Args:
        session_id: Interview session ID

    Returns:
        Question answer analysis list
    """
    logger.info(f"API: Getting topic analysis for session {session_id}")

    try:
        topics = report_analytics_service.analyze_topic_performance(db, session_id)
        return {"session_id": session_id, "topics": topics}
    except Exception as e:
        logger.error(f"Error getting topic analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get topic analysis"
        )


@router.post("/{session_id}/report/export/{export_format}")
async def export_session_report(
    session_id: str,
    export_format: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Export an interview session report as JSON or PDF and return a presigned download URL.

    Args:
        session_id: Interview session ID
        export_format: Export format, either json or pdf

    Returns:
        Export metadata with a presigned download URL
    """
    logger.info(f"API: Exporting {export_format} report for session {session_id}")

    if export_format not in {"json", "pdf"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="export_format must be either 'json' or 'pdf'",
        )

    try:
        return report_export_service.export_report(db, session_id, export_format)
    except ValueError as e:
        logger.error(f"Session not found or invalid export: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Report export dependency error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting session report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export session report",
        )
