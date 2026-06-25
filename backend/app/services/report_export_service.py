"""Session report export service."""

import json
import logging
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Literal
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

from app.models.interview_session import InterviewSession
from app.services.report_analytics_service import report_analytics_service
from app.services.s3_service import s3_service

logger = logging.getLogger(__name__)

ReportExportFormat = Literal["json", "pdf"]


class ReportExportService:
    """Generate downloadable report exports and store them in S3."""

    def export_report(
        self,
        db: Session,
        session_id: str,
        export_format: ReportExportFormat,
    ) -> Dict[str, Any]:
        """Generate a report export, upload it, and return download metadata."""
        logger.info("Exporting %s report for session %s", export_format, session_id)

        session = self._get_session(db, session_id)
        report = report_analytics_service.generate_comprehensive_report(db, session_id)
        generated_at = datetime.utcnow()

        if export_format == "json":
            content = self._build_json_export(report)
            content_type = "application/json"
            extension = "json"
        elif export_format == "pdf":
            content = self._build_pdf_export(report, session)
            content_type = "application/pdf"
            extension = "pdf"
        else:
            raise ValueError(f"Unsupported export format: {export_format}")

        object_key = self._build_object_key(session_id, generated_at, extension)
        file_url = s3_service.upload_file(BytesIO(content), object_key, content_type)
        download_url = s3_service.generate_presigned_url(file_url)

        return {
            "session_id": session_id,
            "format": export_format,
            "content_type": content_type,
            "file_name": object_key.rsplit("/", 1)[-1],
            "object_key": object_key,
            "file_url": file_url,
            "download_url": download_url,
            "generated_at": generated_at.isoformat() + "Z",
        }

    def _get_session(self, db: Session, session_id: str) -> InterviewSession:
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found")
        return session

    def _build_json_export(self, report: Dict[str, Any]) -> bytes:
        return json.dumps(report, ensure_ascii=False, indent=2, default=str).encode("utf-8")

    def _build_pdf_export(self, report: Dict[str, Any], session: InterviewSession) -> bytes:
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_LEFT
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError as exc:
            raise RuntimeError(
                "PDF export requires reportlab. Install backend requirements before exporting PDF."
            ) from exc

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=16 * mm,
            leftMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title="InsightGuide Interview Report",
        )

        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="InsightGuideTitle",
                parent=styles["Title"],
                fontName="STSong-Light",
                fontSize=20,
                leading=26,
                alignment=TA_LEFT,
            )
        )
        styles.add(
            ParagraphStyle(
                name="InsightGuideHeading",
                parent=styles["Heading2"],
                fontName="STSong-Light",
                fontSize=13,
                leading=18,
                spaceBefore=10,
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="InsightGuideBody",
                parent=styles["BodyText"],
                fontName="STSong-Light",
                fontSize=9,
                leading=13,
            )
        )

        story = []
        deck_title = getattr(getattr(session, "deck", None), "title", None) or "Presentation"
        coverage = report["coverage_stats"]
        metrics = report["performance_metrics"]

        story.append(Paragraph("InsightGuide Interview Report", styles["InsightGuideTitle"]))
        story.append(
            Paragraph(f"Document: {self._safe_text(deck_title)}", styles["InsightGuideBody"])
        )
        story.append(
            Paragraph(
                f"Session ID: {self._safe_text(report['session_id'])}",
                styles["InsightGuideBody"],
            )
        )
        story.append(
            Paragraph(
                f"Generated: {self._safe_text(report['generated_at'])}",
                styles["InsightGuideBody"],
            )
        )
        story.append(Spacer(1, 8))

        summary_rows = [
            ["Metric", "Value"],
            ["Overall coverage", f"{coverage['coverage_percentage']}%"],
            ["Must coverage", f"{coverage['must_coverage_percentage']}%"],
            ["Should coverage", f"{coverage['should_coverage_percentage']}%"],
            ["Total topics", str(coverage["total_cards"])],
            [
                "Covered / probably covered",
                f"{coverage['covered']} / {coverage['probably_covered']}",
            ],
            [
                "Skipped / at risk / pending",
                f"{coverage['skipped']} / {coverage['at_risk']} / {coverage['pending']}",
            ],
            ["Duration", self._format_duration(metrics["total_duration_seconds"])],
            ["Utterances", str(metrics["total_utterances"])],
            [
                "Chinese chars per minute",
                str(metrics.get("characters_per_minute", metrics.get("words_per_minute", 0))),
            ],
        ]
        story.append(self._table(summary_rows, Table, TableStyle, colors, mm))

        insights = report.get("insights") or {}
        story.append(Paragraph("Insights", styles["InsightGuideHeading"]))
        for label, key in [
            ("Strengths", "strengths"),
            ("Areas for improvement", "areas_for_improvement"),
            ("Recommendations", "recommendations"),
        ]:
            items = insights.get(key) or []
            if not items:
                continue
            story.append(Paragraph(label, styles["InsightGuideBody"]))
            for item in items[:6]:
                text = item.get("description") or item.get("recommendation") or ""
                story.append(Paragraph(f"- {self._safe_text(text)}", styles["InsightGuideBody"]))

        story.append(Paragraph("Topic Analysis", styles["InsightGuideHeading"]))
        topic_rows = [["Section", "Question", "Importance", "Status", "Confidence"]]
        for topic in report.get("topic_analysis", [])[:40]:
            topic_rows.append(
                [
                    str(topic.get("slide_page") or ""),
                    Paragraph(
                        self._safe_text(topic.get("title") or ""), styles["InsightGuideBody"]
                    ),
                    topic.get("importance") or "",
                    topic.get("status") or "",
                    f"{round((topic.get('confidence') or 0) * 100)}%",
                ]
            )
        story.append(self._table(topic_rows, Table, TableStyle, colors, mm, topic_table=True))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    def _table(
        self,
        rows,
        table_cls,
        table_style_cls,
        colors,
        unit_mm,
        topic_table: bool = False,
    ):
        col_widths = (
            [24 * unit_mm, 88 * unit_mm, 28 * unit_mm, 26 * unit_mm, 24 * unit_mm]
            if topic_table
            else None
        )
        table = table_cls(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            table_style_cls(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eadf")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#2f3a2f")),
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8d2c2")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return table

    def _safe_text(self, value: Any) -> str:
        return escape(str(value))

    def _build_object_key(self, session_id: str, generated_at: datetime, extension: str) -> str:
        timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
        return f"reports/{session_id}/session-report-{timestamp}.{extension}"

    def _format_duration(self, seconds: int | float | None) -> str:
        if not seconds:
            return "0:00"
        minutes = int(seconds) // 60
        remaining_seconds = int(seconds) % 60
        return f"{minutes}:{remaining_seconds:02d}"


report_export_service = ReportExportService()
