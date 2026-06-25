"""Section service for managing section operations."""

import logging
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.section import Section

logger = logging.getLogger(__name__)


class SectionService:
    """Service for section operations."""

    def get_section(self, db: Session, section_id: str) -> Section:
        """Get a section by ID."""
        section = db.query(Section).filter(Section.id == section_id).first()
        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Section {section_id} not found"
            )
        return section

    def get_sections_by_document(self, db: Session, document_id: str) -> List[Section]:
        """Get all sections for a document, ordered by section number."""
        return (
            db.query(Section)
            .filter(Section.document_id == document_id)
            .order_by(Section.section_number)
            .all()
        )


# Singleton instance
section_service = SectionService()
