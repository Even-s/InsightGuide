"""Section service for managing section operations."""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.section import Section
from app.models.document import Document

logger = logging.getLogger(__name__)


class SectionService:
    """Service for section operations."""

    def get_section(self, db: Session, section_id: str) -> Section:
        """Get a section by ID."""
        section = db.query(Section).filter(Section.id == section_id).first()
        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Section {section_id} not found"
            )
        return section

    def get_sections_by_document(self, db: Session, document_id: str) -> List[Section]:
        """Get all sections for a document, ordered by section number."""
        return db.query(Section).filter(
            Section.document_id == document_id
        ).order_by(Section.section_number).all()

    def create_section(
        self,
        db: Session,
        document_id: str,
        section_number: int,
        title: Optional[str] = None,
        extracted_text: Optional[str] = None
    ) -> Section:
        """Create a new section."""
        import uuid
        section_id = f"section_{uuid.uuid4().hex[:12]}"

        section = Section(
            id=section_id,
            document_id=document_id,
            section_number=section_number,
            title=title,
            extracted_text=extracted_text
        )

        db.add(section)
        db.commit()
        db.refresh(section)

        logger.info(f"Created section {section_id} for document {document_id}, section {section_number}")
        return section

    def update_section_summary(self, db: Session, section_id: str, summary: str) -> Section:
        """Update a section's AI summary."""
        section = self.get_section(db, section_id)
        section.ai_summary = summary
        db.commit()
        db.refresh(section)
        logger.info(f"Updated summary for section {section_id}")
        return section


# Singleton instance
section_service = SectionService()
