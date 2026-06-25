"""Worker for AI-powered document analysis and question card generation."""

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.section import Section
from app.services.openai_service import openai_service
# from app.services.document_service import document_service  # Circular import - not used
from app.services.section_service import section_service
from app.services.question_card_service import question_card_service
from app.services.s3_service import s3_service
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


def _snake_to_camel(name: str) -> str:
    components = name.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def _convert_keys_to_camel(obj):
    if isinstance(obj, dict):
        return {_snake_to_camel(k): _convert_keys_to_camel(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_keys_to_camel(item) for item in obj]
    return obj


@celery_app.task(name="analyze_document", bind=True, max_retries=3)
def analyze_document(self, document_id: str):
    """
    Theme-first document analysis pipeline.

    Flow:
    1. Load document + sections
    2. Phase 1: Full-text analysis → generate InterviewThemes
    3. Phase 2: For each theme → generate QuestionCards
    4. Update document status
    """
    logger.info(f"Starting document analysis for document {document_id}")
    db = SessionLocal()

    try:
        from app.services.event_service import event_service
        from app.models.interview_theme import InterviewTheme
        from app.models.question_card import QuestionCard
        import uuid

        # 1. Load document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document {document_id} not found")
            return {"status": "error", "message": "Document not found"}

        if document.status not in ["uploaded", "converted", "analyzing"]:
            return {"status": "skipped", "message": f"Document status is {document.status}"}

        document.status = "analyzing"
        db.commit()
        logger.info(f"Updated document {document_id} status to 'analyzing'")

        # 2. Load or create sections
        sections = section_service.get_sections_by_document(db, document_id)
        if not sections:
            logger.info(f"No sections found, extracting from file...")
            sections = _extract_sections_from_file(db, document)
            if not sections:
                document.status = "failed"
                db.commit()
                return {"status": "error", "message": "No sections could be extracted"}

        logger.info(f"Found {len(sections)} sections for document {document_id}")

        # Build full document text for theme analysis
        full_text = "\n\n".join(
            f"## {s.title or f'Section {s.section_number}'}\n{s.extracted_text or ''}"
            for s in sections
        )

        # 3. Phase 1: Generate interview themes from full document
        logger.info("Phase 1: Generating interview themes...")
        try:
            event_service.publish_sync(document_id, {
                'type': 'ANALYSIS_PROGRESS',
                'message': '正在分析文件，產生訪談單元...',
                'phase': 'themes',
            })
        except Exception:
            pass

        theme_result = openai_service.generate_interview_themes(
            document_title=document.title,
            full_text=full_text,
            sections=sections,
            document_id=document_id,
        )

        # Save interview metadata to document
        document.interview_objective = theme_result.get("interview_objective", "")
        document.interview_priority_order = theme_result.get("priority_order", [])
        document.interview_priority_reasoning = theme_result.get("priority_reasoning", "")
        db.commit()

        # Create InterviewTheme records
        themes_data = theme_result.get("themes", [])
        section_map = {s.section_number: s for s in sections}
        created_themes = []

        for theme_data in themes_data:
            theme_id = f"theme_{uuid.uuid4().hex[:12]}"
            source_section_numbers = theme_data.get("source_section_numbers", [])
            source_section_ids = [
                section_map[n].id for n in source_section_numbers if n in section_map
            ]

            theme = InterviewTheme(
                id=theme_id,
                document_id=document_id,
                theme_number=theme_data.get("theme_number", 0),
                title=theme_data.get("title", "Untitled"),
                rationale=theme_data.get("rationale", ""),
                brd_mapping=theme_data.get("brd_mapping", []),
                priority=theme_data.get("priority", 99),
                estimated_minutes=theme_data.get("estimated_minutes"),
                source_section_ids=source_section_ids,
                order_index=theme_data.get("theme_number", 0),
                is_required=True,
                is_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(theme)
            created_themes.append(theme)

        db.commit()
        logger.info(f"Created {len(created_themes)} interview themes")

        try:
            event_service.publish_sync(document_id, {
                'type': 'THEMES_CREATED',
                'theme_count': len(created_themes),
            })
        except Exception:
            pass

        # 4. Phase 2: For each theme, generate question cards
        logger.info("Phase 2: Generating question cards per theme...")
        total_cards = 0
        total_themes = len(created_themes)
        document_summary = theme_result.get("interview_objective", document.title)

        for theme_index, theme in enumerate(created_themes):
            try:
                logger.info(f"Generating cards for theme {theme.theme_number}: {theme.title}")

                try:
                    event_service.publish_sync(document_id, {
                        'type': 'ANALYSIS_PROGRESS',
                        'message': f'正在為「{theme.title}」產生提問重點...',
                        'phase': 'cards',
                        'current_theme': theme_index + 1,
                        'total_themes': total_themes,
                        'percentage': int((theme_index + 1) / total_themes * 100),
                    })
                except Exception:
                    pass

                # Collect source section text
                source_text_parts = []
                for sec_id in (theme.source_section_ids or []):
                    sec = db.query(Section).filter(Section.id == sec_id).first()
                    if sec and sec.extracted_text:
                        source_text_parts.append(f"### {sec.title or ''}\n{sec.extracted_text}")

                source_sections_text = "\n\n".join(source_text_parts) if source_text_parts else full_text[:4000]

                # Call OpenAI to generate cards for this theme
                cards_result = openai_service.generate_theme_question_cards(
                    document_title=document.title,
                    document_summary=document_summary,
                    theme_title=theme.title,
                    theme_rationale=theme.rationale,
                    theme_brd_mapping=theme.brd_mapping or [],
                    source_sections_text=source_sections_text,
                    document_id=document_id,
                )

                # Create QuestionCard records
                cards_data = cards_result.get("cards", [])
                first_source_section_id = (theme.source_section_ids or [None])[0]

                for card_index, card_data in enumerate(cards_data):
                    try:
                        raw_importance = card_data.get("importance", "should")
                        importance = "must" if raw_importance in ("must", "high", "critical") else "should"

                        raw_coverage = card_data.get("coverage_rule")
                        coverage_rule = _convert_keys_to_camel(raw_coverage) if raw_coverage else {
                            "semanticAnchors": [],
                            "expectedKeywords": [],
                            "mustMentionElements": [],
                            "thresholds": {"probablySufficient": 0.65, "sufficient": 0.80}
                        }

                        card_id = f"qcard_{uuid.uuid4().hex[:12]}"
                        card = QuestionCard(
                            id=card_id,
                            document_id=document_id,
                            interview_theme_id=theme.id,
                            section_id=first_source_section_id,
                            section_number=theme.theme_number,
                            focus_text=card_data.get("focus_text", ""),
                            question_text=(card_data.get("question_text", "") or "")[:200] or "Untitled",
                            question_type=card_data.get("question_type", "clarification"),
                            importance=importance,
                            coverage_rule=coverage_rule,
                            suggested_followup=card_data.get("suggested_followup", ""),
                            expected_answer_elements=card_data.get("expected_answer_elements", []),
                            brd_mapping=card_data.get("brd_mapping", []),
                            estimated_seconds=90,
                            order_index=card_index,
                            status="pending",
                            ui={"color": "default", "isVisible": True, "isPinned": False, "displayMode": "full"},
                            created_by="ai",
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                        )
                        db.add(card)
                        total_cards += 1

                    except Exception as card_err:
                        logger.error(f"Failed to create card for theme {theme.id}: {card_err}", exc_info=True)
                        continue

                db.commit()
                logger.info(f"Created {len(cards_data)} cards for theme {theme.title}")

                try:
                    event_service.publish_sync(document_id, {
                        'type': 'THEME_CARDS_CREATED',
                        'theme_id': theme.id,
                        'theme_title': theme.title,
                        'card_count': len(cards_data),
                        'total_cards': total_cards,
                    })
                except Exception:
                    pass

            except Exception as theme_err:
                logger.error(f"Failed to generate cards for theme {theme.id}: {theme_err}", exc_info=True)
                continue

        # 5. Finalize
        document.status = "analyzed"
        document.updated_at = datetime.utcnow()
        db.commit()

        # Update prep session to ready
        try:
            from app.models.prep_session import PrepSession
            prep_session = db.query(PrepSession).filter(PrepSession.id == document_id).first()
            if prep_session and prep_session.status == "preparing":
                prep_session.status = "ready"
                prep_session.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Updated prep session {document_id} to 'ready'")
        except Exception as ps_err:
            logger.warning(f"Failed to update prep session status: {ps_err}")

        logger.info(
            f"Document analysis complete for {document_id}. "
            f"Generated {len(created_themes)} themes, {total_cards} cards"
        )

        try:
            event_service.publish_sync(document_id, {
                'type': 'ANALYSIS_COMPLETE',
                'document_id': document_id,
                'total_themes': len(created_themes),
                'total_cards': total_cards,
            })
        except Exception:
            pass

        return {
            "status": "success",
            "document_id": document_id,
            "total_themes": len(created_themes),
            "total_cards": total_cards,
        }

    except Exception as e:
        logger.error(f"Document analysis failed for {document_id}: {e}", exc_info=True)

        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = "failed"
                db.commit()
        except Exception:
            pass

        raise self.retry(exc=e, countdown=60)

    finally:
        db.close()


def build_section_analysis_prompt(section_title: str, section_text: str, document_title: str) -> str:
    """
    Build a prompt for OpenAI to analyze a document section.

    Args:
        section_title: Title of the section
        section_text: Text content of the section
        document_title: Title of the document

    Returns:
        Formatted prompt string
    """
    return f"""You are analyzing a requirements document section for a requirements gathering interview.

Document: {document_title}
Section: {section_title}

Section Content:
{section_text}

Your task is to:
1. Summarize the key requirements in this section
2. Generate interview questions to clarify, validate, and explore these requirements
3. For each question, provide expected answer elements that would make the answer sufficient

Generate questions in these categories:
- Clarification: Questions to understand ambiguous or unclear requirements
- Validation: Questions to verify understanding and confirm requirements
- Exploration: Questions to uncover edge cases, constraints, and hidden requirements

For each question, include:
- The question text (open-ended, encouraging detailed answers)
- The question type (clarification, validation, or exploration)
- Importance (must: critical requirements, should: important but not critical)
- Expected answer elements (key points that should be covered in a sufficient answer)
- A suggested followup question if the initial answer is insufficient

Output format: JSON
"""


def analyze_section_with_retry(section_id: str, max_retries: int = 3) -> dict:
    """
    Analyze a single section with retry logic.

    Args:
        section_id: ID of the section to analyze
        max_retries: Maximum number of retry attempts

    Returns:
        Analysis result dictionary
    """
    db = SessionLocal()

    try:
        section = section_service.get_section(db, section_id)
        if not section:
            return {"status": "error", "message": "Section not found"}

        for attempt in range(max_retries):
            try:
                analysis_result = openai_service.analyze_document_section(
                    section_text=section.extracted_text,
                    section_title=section.title,
                    document_title=section.document.title if section.document else "Unknown",
                    section_number=section.section_number
                )
                return {"status": "success", "result": analysis_result}

            except Exception as e:
                logger.warning(f"Section analysis attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise

    finally:
        db.close()


def _extract_sections_from_file(db, document: Document) -> list:
    """
    Extract sections from a document file (supports .md and .txt).
    Downloads file from S3, parses it into sections by headings, and saves to DB.
    """
    import re
    import uuid
    from io import BytesIO

    try:
        object_key = document.source_file_url.split("/insightguide-uploads/")[-1] if "insightguide-uploads/" in document.source_file_url else document.source_file_url
        file_content = s3_service.download_file(object_key)

        if isinstance(file_content, BytesIO):
            text = file_content.read().decode("utf-8")
        elif isinstance(file_content, bytes):
            text = file_content.decode("utf-8")
        else:
            text = str(file_content)

    except Exception as e:
        logger.error(f"Failed to download file for document {document.id}: {e}")
        return []

    if not text.strip():
        logger.warning(f"Document {document.id} file is empty")
        return []

    sections_data = _parse_markdown_sections(text)

    if not sections_data:
        sections_data = [{"title": document.title or "Content", "text": text.strip()}]

    created_sections = []
    for idx, section_data in enumerate(sections_data, start=1):
        section = Section(
            id=f"sec_{uuid.uuid4().hex[:12]}",
            document_id=document.id,
            section_number=idx,
            title=section_data["title"],
            extracted_text=section_data["text"],
            created_at=datetime.utcnow(),
        )
        db.add(section)
        created_sections.append(section)

    db.commit()
    logger.info(f"Created {len(created_sections)} sections for document {document.id}")
    return created_sections


def _parse_markdown_sections(text: str) -> list:
    """Parse markdown text into sections based on headings."""
    import re

    lines = text.split("\n")
    sections = []
    current_title = None
    current_lines = []

    for line in lines:
        heading_match = re.match(r'^(#{1,3})\s+(.+)$', line)
        if heading_match:
            if current_title and current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append({"title": current_title, "text": content})
            current_title = heading_match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_title and current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append({"title": current_title, "text": content})

    if not sections and current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append({"title": "Document Content", "text": content})

    return sections
