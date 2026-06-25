"""Evidence Matrix routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.evidence_matrix_service import evidence_matrix_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _entry_to_response(entry) -> dict:
    return {
        "id": entry.id,
        "matrixId": entry.matrix_id,
        "requirementCandidate": entry.requirement_candidate,
        "category": entry.category,
        "sourceRoles": entry.source_roles or [],
        "sourceMemoIds": entry.source_memo_ids or [],
        "supportingEvidence": entry.supporting_evidence or [],
        "conflicts": entry.conflicts or [],
        "validationStatus": entry.validation_status,
        "missingValidationFrom": entry.missing_validation_from or [],
        "mentionCount": entry.mention_count,
        "stakeholderAgreementLevel": entry.stakeholder_agreement_level,
        "createdAt": entry.created_at.isoformat() if entry.created_at else None,
        "updatedAt": entry.updated_at.isoformat() if entry.updated_at else None,
    }


@router.get("/projects/{project_id}/evidence-matrix")
async def get_evidence_matrix(project_id: str, db: Session = Depends(get_db)):
    """Get the requirement evidence matrix for a project."""
    from app.models.requirement_evidence_matrix import (
        EvidenceMatrixEntry,
        RequirementEvidenceMatrix,
    )

    matrix = (
        db.query(RequirementEvidenceMatrix)
        .filter(RequirementEvidenceMatrix.project_id == project_id)
        .first()
    )

    if not matrix:
        return {
            "matrix": None,
            "entries": [],
            "summary": evidence_matrix_service.get_matrix_summary(db, project_id),
        }

    entries = (
        db.query(EvidenceMatrixEntry)
        .filter(EvidenceMatrixEntry.matrix_id == matrix.id)
        .order_by(EvidenceMatrixEntry.mention_count.desc())
        .all()
    )

    return {
        "matrix": {
            "id": matrix.id,
            "projectId": matrix.project_id,
            "status": matrix.status,
            "memoCount": matrix.memo_count,
            "lastUpdatedAt": matrix.last_updated_at.isoformat() if matrix.last_updated_at else None,
            "markdownContent": matrix.markdown_content,
        },
        "entries": [_entry_to_response(e) for e in entries],
        "summary": evidence_matrix_service.get_matrix_summary(db, project_id),
    }


@router.post("/projects/{project_id}/evidence-matrix/refresh")
async def refresh_evidence_matrix(project_id: str, db: Session = Depends(get_db)):
    """Refresh (rebuild) the evidence matrix from all insight memos."""
    try:
        matrix = evidence_matrix_service.update_matrix(db, project_id)
    except Exception as e:
        logger.error(f"Failed to refresh evidence matrix: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to refresh evidence matrix")

    from app.models.requirement_evidence_matrix import EvidenceMatrixEntry

    entries = (
        db.query(EvidenceMatrixEntry)
        .filter(EvidenceMatrixEntry.matrix_id == matrix.id)
        .order_by(EvidenceMatrixEntry.mention_count.desc())
        .all()
    )

    return {
        "matrix": {
            "id": matrix.id,
            "projectId": matrix.project_id,
            "status": matrix.status,
            "memoCount": matrix.memo_count,
            "lastUpdatedAt": matrix.last_updated_at.isoformat() if matrix.last_updated_at else None,
        },
        "entries": [_entry_to_response(e) for e in entries],
        "summary": evidence_matrix_service.get_matrix_summary(db, project_id),
    }


@router.put("/evidence-matrix-entries/{entry_id}")
async def update_matrix_entry(
    entry_id: str,
    data: dict,
    db: Session = Depends(get_db),
):
    """Manually update an evidence matrix entry (e.g. mark as rejected)."""
    allowed_fields = {"validation_status", "category", "conflicts", "missing_validation_from"}
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    entry = evidence_matrix_service.update_entry(db, entry_id, update_data)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    return _entry_to_response(entry)


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
