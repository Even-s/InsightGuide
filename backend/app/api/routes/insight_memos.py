"""Interview Insight Memo routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.insight_memo_service import insight_memo_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _memo_to_response(memo) -> dict:
    """Convert InterviewInsightMemo to API response."""
    return {
        "id": memo.id,
        "sessionId": memo.session_id,
        "projectId": memo.project_id,
        "stakeholderProfileId": memo.stakeholder_profile_id,
        "interviewDate": memo.interview_date.isoformat() if memo.interview_date else None,
        "interviewDurationMinutes": memo.interview_duration_minutes,
        "topicsCovered": memo.topics_covered or [],
        "stakeholderSummary": memo.stakeholder_summary,
        "qaSummaries": memo.qa_summaries or [],
        "painPoints": memo.pain_points or [],
        "requirementCandidates": memo.requirement_candidates or [],
        "constraintsAndAssumptions": memo.constraints_and_assumptions or [],
        "processDescriptions": memo.process_descriptions or [],
        "unresolvedQuestions": memo.unresolved_questions or [],
        "nextInterviewSuggestions": memo.next_interview_suggestions or [],
        "sourceDistinction": memo.source_distinction,
        "markdownContent": memo.markdown_content,
        "status": memo.status,
        "generatedAt": memo.generated_at.isoformat() if memo.generated_at else None,
        "createdAt": memo.created_at.isoformat() if memo.created_at else None,
    }


@router.post("/sessions/{session_id}/insight-memo", status_code=status.HTTP_201_CREATED)
async def generate_insight_memo(session_id: str, db: Session = Depends(get_db)):
    """Generate an Interview Insight Memo. Returns existing one if already generated."""
    existing = insight_memo_service.get_memo(db, session_id)
    if existing:
        return _memo_to_response(existing)

    try:
        memo = insight_memo_service.generate_memo(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate insight memo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate insight memo")

    return _memo_to_response(memo)


@router.get("/sessions/{session_id}/insight-memo")
async def get_insight_memo(session_id: str, db: Session = Depends(get_db)):
    """Get the Insight Memo for a session."""
    memo = insight_memo_service.get_memo(db, session_id)
    if not memo:
        raise HTTPException(status_code=404, detail="No insight memo found for this session")
    return _memo_to_response(memo)


@router.get("/projects/{project_id}/insight-memos")
async def list_project_insight_memos(project_id: str, db: Session = Depends(get_db)):
    """List all insight memos for a project."""
    memos = insight_memo_service.get_memos_for_project(db, project_id)
    return {
        "memos": [_memo_to_response(m) for m in memos],
        "total": len(memos),
    }
