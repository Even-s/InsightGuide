"""Evidence Matrix routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.evidence_matrix_service import evidence_matrix_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _derived_entry_to_response(project_id: str, entry: dict, index: int) -> dict:
    return {
        "id": f"derived_{project_id}_{index + 1}",
        "matrixId": f"round_aggregate:{project_id}",
        "requirementCandidate": entry.get("requirement_candidate", ""),
        "category": entry.get("category"),
        "sourceRoles": entry.get("source_roles", []) or [],
        "sourceMemoIds": entry.get("source_memo_ids", []) or [],
        "supportingEvidence": entry.get("supporting_evidence", []) or [],
        "conflicts": entry.get("conflicts", []) or [],
        "validationStatus": entry.get("validation_status", "candidate"),
        "missingValidationFrom": entry.get("missing_validation_from", []) or [],
        "mentionCount": entry.get("mention_count", 0),
        "stakeholderAgreementLevel": entry.get("stakeholder_agreement_level"),
        "createdAt": None,
        "updatedAt": None,
        "editable": False,
        "source": "round_aggregate",
    }


@router.get("/projects/{project_id}/evidence-matrix")
async def get_evidence_matrix(project_id: str, db: Session = Depends(get_db)):
    """Get the requirement evidence matrix derived directly from RoundAggregate."""
    entries, memos = evidence_matrix_service.build_entries_from_round_aggregates(db, project_id)
    summary = evidence_matrix_service.summarize_entries(entries, memos)

    if not memos:
        return {
            "matrix": None,
            "entries": [],
            "summary": summary,
        }

    entries = sorted(entries, key=lambda entry: entry.get("mention_count", 0), reverse=True)

    return {
        "matrix": {
            "id": f"round_aggregate:{project_id}",
            "projectId": project_id,
            "status": "derived",
            "memoCount": len(memos),
            "lastUpdatedAt": summary.get("last_updated_at"),
            "markdownContent": evidence_matrix_service._render_matrix_markdown(entries),
            "source": "round_aggregate",
            "editable": False,
        },
        "entries": [
            _derived_entry_to_response(project_id, entry, index)
            for index, entry in enumerate(entries)
        ],
        "summary": summary,
    }


@router.post("/projects/{project_id}/evidence-matrix/refresh")
async def refresh_evidence_matrix(project_id: str, db: Session = Depends(get_db)):
    """Refresh (rebuild) the evidence matrix from ready RoundAggregate outputs."""
    try:
        matrix = evidence_matrix_service.update_matrix(db, project_id)
    except Exception as e:
        logger.error(f"Failed to refresh evidence matrix: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to refresh evidence matrix")

    entries = sorted(
        getattr(matrix, "_derived_entries", []) or [],
        key=lambda entry: entry.get("mention_count", 0),
        reverse=True,
    )
    memos = getattr(matrix, "_source_memos", []) or []

    return {
        "matrix": {
            "id": matrix.id,
            "projectId": matrix.project_id,
            "status": matrix.status,
            "memoCount": matrix.memo_count,
            "lastUpdatedAt": matrix.last_updated_at.isoformat() if matrix.last_updated_at else None,
            "source": "round_aggregate",
            "editable": False,
        },
        "entries": [
            _derived_entry_to_response(project_id, entry, index)
            for index, entry in enumerate(entries)
        ],
        "summary": evidence_matrix_service.summarize_entries(entries, memos, status=matrix.status),
    }


@router.get("/projects/{project_id}/interview-suggestions")
async def get_interview_suggestions(project_id: str, db: Session = Depends(get_db)):
    """Get next interview suggestions based on evidence gaps."""
    summary = evidence_matrix_service.get_matrix_summary(db, project_id)

    suggestions = []
    for role in summary.get("roles_missing", []):
        suggestions.append(
            {
                "target_role": role,
                "reason": f"有候選需求等待 {role} 角色驗證",
                "urgency": "high" if summary.get("needs_more_evidence", 0) > 2 else "medium",
            }
        )

    return {
        "suggestions": suggestions,
        "summary": summary,
    }
