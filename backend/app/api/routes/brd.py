"""BRD (Business Requirements Document) API routes."""

import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.brd import BRDDraft, Requirement
from app.models.user import User
from app.schemas.brd import (
    BRDDraftResponse,
    BRDExportRequest,
    BRDExportResponse,
    BRDGenerationRequest,
    BRDGenerationResponse,
    RequirementResponse,
    RequirementUpdate,
)
from app.services.brd_generator_service import brd_generator_service
from app.services.brd_pdf_export_service import brd_pdf_export_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# BRD Draft Endpoints
# ============================================================================


@router.post("/generate", response_model=BRDGenerationResponse)
def generate_brd(
    request: BRDGenerationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate BRD from a completed interview session.

    This endpoint initiates BRD generation in the background.
    Use the returned brd_id to poll for status.
    """
    try:
        # Start generation in background
        def generate_in_background():
            try:
                brd_generator_service.generate_brd(db, request.interview_session_id)
            except Exception as e:
                logger.error(f"BRD generation failed: {e}", exc_info=True)

        background_tasks.add_task(generate_in_background)

        # Return immediate response
        brd_id = f"brd_{request.interview_session_id[:12]}"

        return BRDGenerationResponse(
            brd_id=brd_id,
            status="generating",
            message="BRD generation started. Use GET /api/brd/{brd_id} to check status.",
        )

    except Exception as e:
        logger.error(f"Failed to initiate BRD generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{brd_id}", response_model=BRDDraftResponse)
def get_brd(
    brd_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get BRD draft by ID.

    Returns the complete BRD with all requirements.
    """
    brd = (
        db.query(BRDDraft)
        .filter(BRDDraft.id == brd_id, BRDDraft.user_id == current_user.id)
        .first()
    )

    if not brd:
        raise HTTPException(status_code=404, detail="BRD not found")

    return brd


@router.get("/session/{session_id}", response_model=BRDDraftResponse)
def get_brd_by_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get BRD draft by interview session ID.

    Returns the BRD associated with the given interview session.
    """
    brd = (
        db.query(BRDDraft)
        .filter(BRDDraft.interview_session_id == session_id, BRDDraft.user_id == current_user.id)
        .first()
    )

    if not brd:
        raise HTTPException(status_code=404, detail="BRD not found for this session")

    return brd


@router.post("/{brd_id}/export", response_model=BRDExportResponse)
def export_brd(
    brd_id: str,
    request: BRDExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export BRD to specified format.

    Supported formats: markdown, pdf, docx
    """
    brd = (
        db.query(BRDDraft)
        .filter(BRDDraft.id == brd_id, BRDDraft.user_id == current_user.id)
        .first()
    )

    if not brd:
        raise HTTPException(status_code=404, detail="BRD not found")

    if brd.status != "completed":
        raise HTTPException(status_code=400, detail="BRD generation is not complete yet")

    try:
        from datetime import datetime

        # Generate download URL based on format
        if request.format == "markdown":
            download_url = f"/api/brd/{brd_id}/download/markdown"
        elif request.format == "pdf":
            download_url = f"/api/brd/{brd_id}/download/pdf"
        elif request.format == "docx":
            raise HTTPException(
                status_code=501, detail="DOCX export is not yet available. Use PDF or Markdown."
            )
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported export format: {request.format}"
            )

        brd.last_exported_at = datetime.utcnow()
        db.commit()

        return BRDExportResponse(
            brd_id=brd_id,
            format=request.format,
            download_url=download_url,
            exported_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export BRD: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{brd_id}/download/markdown")
def download_brd_markdown(
    brd_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download BRD as Markdown file.
    """
    from fastapi.responses import PlainTextResponse

    brd = (
        db.query(BRDDraft)
        .filter(BRDDraft.id == brd_id, BRDDraft.user_id == current_user.id)
        .first()
    )

    if not brd:
        raise HTTPException(status_code=404, detail="BRD not found")

    if not brd.markdown_content:
        raise HTTPException(status_code=400, detail="Markdown content not available")

    filename = f"{brd.title or 'BRD'}.md".replace(" ", "_")

    return PlainTextResponse(
        content=brd.markdown_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{brd_id}/download/pdf")
def download_brd_pdf(
    brd_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download BRD as PDF file.
    """
    from fastapi.responses import StreamingResponse

    brd = (
        db.query(BRDDraft)
        .filter(BRDDraft.id == brd_id, BRDDraft.user_id == current_user.id)
        .first()
    )

    if not brd:
        raise HTTPException(status_code=404, detail="BRD not found")

    if brd.status != "completed":
        raise HTTPException(status_code=400, detail="BRD generation is not complete yet")

    try:
        # Generate PDF using the export service
        pdf_buffer = brd_pdf_export_service.generate_pdf(brd)

        filename = f"{brd.title or 'BRD'}.pdf".replace(" ", "_")

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


# ============================================================================
# Requirements Endpoints
# ============================================================================


@router.get("/{brd_id}/requirements", response_model=List[RequirementResponse])
def get_requirements(
    brd_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all requirements for a BRD.
    """
    # Verify BRD ownership
    brd = (
        db.query(BRDDraft)
        .filter(BRDDraft.id == brd_id, BRDDraft.user_id == current_user.id)
        .first()
    )

    if not brd:
        raise HTTPException(status_code=404, detail="BRD not found")

    requirements = db.query(Requirement).filter(Requirement.brd_draft_id == brd_id).all()

    return requirements


@router.patch("/{brd_id}/requirements/{requirement_id}", response_model=RequirementResponse)
def update_requirement(
    brd_id: str,
    requirement_id: str,
    request: RequirementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a specific requirement.

    Allows manual editing of generated requirements.
    """
    # Verify BRD ownership
    brd = (
        db.query(BRDDraft)
        .filter(BRDDraft.id == brd_id, BRDDraft.user_id == current_user.id)
        .first()
    )

    if not brd:
        raise HTTPException(status_code=404, detail="BRD not found")

    # Get requirement
    requirement = (
        db.query(Requirement)
        .filter(Requirement.id == requirement_id, Requirement.brd_draft_id == brd_id)
        .first()
    )

    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")

    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(requirement, field, value)

    db.commit()
    db.refresh(requirement)

    return requirement


@router.delete("/{brd_id}/requirements/{requirement_id}")
def delete_requirement(
    brd_id: str,
    requirement_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a specific requirement.
    """
    # Verify BRD ownership
    brd = (
        db.query(BRDDraft)
        .filter(BRDDraft.id == brd_id, BRDDraft.user_id == current_user.id)
        .first()
    )

    if not brd:
        raise HTTPException(status_code=404, detail="BRD not found")

    # Get requirement
    requirement = (
        db.query(Requirement)
        .filter(Requirement.id == requirement_id, Requirement.brd_draft_id == brd_id)
        .first()
    )

    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")

    db.delete(requirement)
    db.commit()

    return {"message": "Requirement deleted successfully"}
