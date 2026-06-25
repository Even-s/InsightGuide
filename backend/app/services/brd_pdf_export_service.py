"""
BRD PDF Export Service
Generates professional PDF documents from BRD drafts using ReportLab.
"""

import logging
from datetime import datetime
from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.brd import BRDDraft, Requirement

logger = logging.getLogger(__name__)


class BRDPDFExportService:
    """Service for exporting BRD drafts to PDF format."""

    def __init__(self):
        """Initialize PDF export service."""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles for the PDF."""
        # Title style
        self.styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor("#1e3a8a"),
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            )
        )

        # Heading 1 style
        self.styles.add(
            ParagraphStyle(
                name="CustomHeading1",
                parent=self.styles["Heading1"],
                fontSize=16,
                textColor=colors.HexColor("#2563eb"),
                spaceAfter=12,
                spaceBefore=20,
                fontName="Helvetica-Bold",
            )
        )

        # Heading 2 style
        self.styles.add(
            ParagraphStyle(
                name="CustomHeading2",
                parent=self.styles["Heading2"],
                fontSize=14,
                textColor=colors.HexColor("#3b82f6"),
                spaceAfter=10,
                spaceBefore=15,
                fontName="Helvetica-Bold",
            )
        )

        # Body text style
        self.styles.add(
            ParagraphStyle(
                name="CustomBody",
                parent=self.styles["BodyText"],
                fontSize=11,
                leading=16,
                alignment=TA_JUSTIFY,
                spaceAfter=10,
            )
        )

        # Bullet list style
        self.styles.add(
            ParagraphStyle(
                name="CustomBullet",
                parent=self.styles["BodyText"],
                fontSize=11,
                leading=16,
                leftIndent=20,
                spaceAfter=6,
            )
        )

    def generate_pdf(self, brd: BRDDraft) -> BytesIO:
        """
        Generate PDF from BRD draft.

        Args:
            brd: BRDDraft instance to export

        Returns:
            BytesIO: PDF file content in memory
        """
        buffer = BytesIO()

        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        # Build document content
        story = []

        # Title page
        story.extend(self._build_title_page(brd))

        # Table of Contents
        # story.extend(self._build_table_of_contents(brd))
        # story.append(PageBreak())

        # Executive Summary
        if brd.executive_summary:
            story.extend(self._build_section("Executive Summary", brd.executive_summary))

        # Project Overview
        if brd.project_overview:
            story.extend(self._build_section("Project Overview", brd.project_overview))

        # Business Objectives
        if brd.business_objectives:
            story.extend(self._build_list_section("Business Objectives", brd.business_objectives))

        # Success Criteria
        if brd.success_criteria:
            story.extend(self._build_list_section("Success Criteria", brd.success_criteria))

        # Stakeholders
        if brd.stakeholders:
            story.extend(self._build_stakeholders_section(brd.stakeholders))

        # Requirements
        if brd.requirements:
            story.extend(self._build_requirements_section(brd.requirements))

        # Assumptions
        if brd.assumptions:
            story.extend(self._build_list_section("Assumptions", brd.assumptions))

        # Constraints
        if brd.constraints:
            story.extend(self._build_list_section("Constraints", brd.constraints))

        # Risks
        if brd.risks:
            story.extend(self._build_risks_section(brd.risks))

        # Build PDF
        doc.build(story)

        buffer.seek(0)
        return buffer

    def _build_title_page(self, brd: BRDDraft) -> list:
        """Build title page elements."""
        elements = []

        # Spacer to center title
        elements.append(Spacer(1, 2 * inch))

        # Title
        title = brd.title or "Business Requirements Document"
        elements.append(Paragraph(title, self.styles["CustomTitle"]))
        elements.append(Spacer(1, 0.5 * inch))

        # Metadata table
        metadata_data = [
            ["Document ID:", str(brd.id)[:8]],
            [
                "Generated:",
                brd.generated_at.strftime("%Y-%m-%d %H:%M") if brd.generated_at else "N/A",
            ],
            ["Status:", brd.status.value.replace("_", " ").title()],
        ]

        metadata_table = Table(metadata_data, colWidths=[2 * inch, 4 * inch])
        metadata_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(metadata_table)

        # Page break after title
        elements.append(PageBreak())

        return elements

    def _build_section(self, title: str, content: str) -> list:
        """Build a standard text section."""
        elements = []
        elements.append(Paragraph(title, self.styles["CustomHeading1"]))
        elements.append(Spacer(1, 0.1 * inch))

        # Split content into paragraphs
        paragraphs = content.split("\n\n")
        for para in paragraphs:
            if para.strip():
                elements.append(Paragraph(para.strip(), self.styles["CustomBody"]))
                elements.append(Spacer(1, 0.1 * inch))

        elements.append(Spacer(1, 0.2 * inch))
        return elements

    def _build_list_section(self, title: str, items: list) -> list:
        """Build a section with a bulleted list."""
        elements = []
        elements.append(Paragraph(title, self.styles["CustomHeading1"]))
        elements.append(Spacer(1, 0.1 * inch))

        for item in items:
            bullet_text = f"• {item}"
            elements.append(Paragraph(bullet_text, self.styles["CustomBullet"]))

        elements.append(Spacer(1, 0.2 * inch))
        return elements

    def _build_stakeholders_section(self, stakeholders: list) -> list:
        """Build stakeholders section with table."""
        elements = []
        elements.append(Paragraph("Stakeholders", self.styles["CustomHeading1"]))
        elements.append(Spacer(1, 0.1 * inch))

        # Build table data
        table_data = [["Role", "Name"]]
        for sh in stakeholders:
            table_data.append([sh.get("role", ""), sh.get("name", "")])

        table = Table(table_data, colWidths=[2 * inch, 4 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _build_requirements_section(self, requirements: list[Requirement]) -> list:
        """Build requirements section with detailed cards."""
        elements = []
        elements.append(Paragraph("Requirements", self.styles["CustomHeading1"]))
        elements.append(Spacer(1, 0.2 * inch))

        for req in requirements:
            # Keep each requirement together on the same page
            req_elements = []

            # Requirement title with priority and type badges
            priority_label = req.priority.value.replace("_", " ").title()
            type_label = req.type.value.replace("_", " ").title()
            title_text = f"<b>{req.title}</b> [{priority_label}] [{type_label}]"
            req_elements.append(Paragraph(title_text, self.styles["CustomHeading2"]))
            req_elements.append(Spacer(1, 0.05 * inch))

            # Description
            req_elements.append(Paragraph(req.description, self.styles["CustomBody"]))
            req_elements.append(Spacer(1, 0.1 * inch))

            # User story (if exists)
            if req.user_story:
                req_elements.append(Paragraph("<b>User Story:</b>", self.styles["CustomBody"]))
                req_elements.append(Paragraph(req.user_story, self.styles["CustomBullet"]))
                req_elements.append(Spacer(1, 0.1 * inch))

            # Acceptance criteria (if exists)
            if req.acceptance_criteria:
                req_elements.append(
                    Paragraph("<b>Acceptance Criteria:</b>", self.styles["CustomBody"])
                )
                for criteria in req.acceptance_criteria:
                    req_elements.append(Paragraph(f"• {criteria}", self.styles["CustomBullet"]))
                req_elements.append(Spacer(1, 0.1 * inch))

            # Add border box around requirement
            elements.append(KeepTogether(req_elements))
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _build_risks_section(self, risks: list) -> list:
        """Build risks section with mitigation strategies."""
        elements = []
        elements.append(Paragraph("Risks", self.styles["CustomHeading1"]))
        elements.append(Spacer(1, 0.2 * inch))

        for risk in risks:
            risk_elements = []

            # Risk description
            risk_elements.append(
                Paragraph(
                    f"<b>Risk:</b> {risk.get('description', '')}",
                    self.styles["CustomBody"],
                )
            )
            risk_elements.append(Spacer(1, 0.05 * inch))

            # Mitigation
            if risk.get("mitigation"):
                risk_elements.append(
                    Paragraph(
                        f"<b>Mitigation:</b> {risk['mitigation']}",
                        self.styles["CustomBody"],
                    )
                )

            elements.append(KeepTogether(risk_elements))
            elements.append(Spacer(1, 0.15 * inch))

        elements.append(Spacer(1, 0.2 * inch))
        return elements


# Global service instance
brd_pdf_export_service = BRDPDFExportService()
