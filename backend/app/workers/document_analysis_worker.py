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
    Analyze requirements document using OpenAI API and generate question cards.

    This worker implements document analysis functionality:
    1. Load document and sections from database
    2. Call OpenAI API to analyze each section
    3. Generate section summaries
    4. Generate question cards for each section
    5. Generate expected answer elements
    6. Generate suggested followup questions
    7. Save results to database
    8. Update document status to 'analyzed'
    """
    logger.info(f"Starting document analysis for document {document_id}")
    db = SessionLocal()

    try:
        # 1. Load document and verify it's ready for analysis
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document {document_id} not found")
            return {"status": "error", "message": "Document not found"}

        if document.status not in ["uploaded", "converted", "analyzing"]:
            logger.warning(
                f"Document {document_id} is not ready for analysis. "
                f"Current status: {document.status}"
            )
            return {
                "status": "skipped",
                "message": f"Document status is {document.status}, not ready for analysis"
            }

        # Update document status to analyzing
        document.status = "analyzing"
        db.commit()
        logger.info(f"Updated document {document_id} status to 'analyzing'")

        # 2. Load or create sections for this document
        sections = section_service.get_sections_by_document(db, document_id)
        if not sections:
            logger.info(f"No sections found for document {document_id}, extracting from file...")
            sections = _extract_sections_from_file(db, document)
            if not sections:
                logger.error(f"Failed to extract sections from document {document_id}")
                document.status = "failed"
                db.commit()
                return {"status": "error", "message": "No sections could be extracted from file"}

        logger.info(f"Found {len(sections)} sections to analyze for document {document_id}")

        # 3. Analyze each section
        total_cards = 0
        total_sections = len(sections)

        # Import event service for SSE
        from app.services.event_service import event_service

        for section_index, section in enumerate(sections):
            try:
                logger.info(
                    f"Analyzing section {section.id} "
                    f"(section {section.section_number}/{len(sections)})"
                )

                existing_cards = question_card_service.get_question_cards_by_section(db, section.id)
                if section.ai_summary and existing_cards:
                    total_cards += len(existing_cards)
                    logger.info(
                        f"Skipping section {section.id}; summary and "
                        f"{len(existing_cards)} question cards already exist"
                    )
                    continue

                # Get section text for analysis
                if not section.extracted_text:
                    logger.warning(f"Section {section.id} has no text content, skipping")
                    continue

                # Build the analysis prompt for this section
                analysis_prompt = build_section_analysis_prompt(
                    section.title or f"Section {section.section_number}",
                    section.extracted_text,
                    document.title
                )

                # Send progress event
                try:
                    event_service.publish_sync(document_id, {
                        'type': 'ANALYSIS_PROGRESS',
                        'current_section': section_index + 1,
                        'total_sections': total_sections,
                        'total_cards': total_cards,
                        'message': f"Analyzing section {section.section_number}"
                    })
                except Exception:
                    pass

                # Call OpenAI to analyze the section
                logger.info(f"Calling OpenAI to analyze section {section.id}")
                analysis_result = openai_service.analyze_document_section(
                    section_text=section.extracted_text,
                    section_title=section.title,
                    document_title=document.title,
                    section_number=section.section_number
                )

                # Update section with AI summary
                if analysis_result.get("summary"):
                    section.ai_summary = analysis_result["summary"]
                    db.commit()
                    logger.info(f"Updated section {section.id} with AI summary")

                # Generate question cards for this section
                if analysis_result.get("questions"):
                    questions = analysis_result["questions"]
                    logger.info(f"Generating {len(questions)} question cards for section {section.id}")

                    from app.schemas.question_card import QuestionCardCreate

                    for question_data in questions:
                        try:
                            # Normalize importance: OpenAI may return "high"/"medium"/"low"
                            raw_importance = question_data.get("importance", "should")
                            importance = "must" if raw_importance in ("must", "high", "critical") else "should"

                            raw_coverage = question_data.get("coverage_rule")
                            coverage_rule = _convert_keys_to_camel(raw_coverage) if raw_coverage else None

                            card_create = QuestionCardCreate(
                                sectionId=section.id,
                                questionText=question_data.get("question_text", "")[:200] or "Untitled Question",
                                questionType=question_data.get("question_type", "clarification"),
                                importance=importance,
                                suggestedFollowup=question_data.get("suggested_followup") or "Could you elaborate on that?",
                                expectedAnswerElements=question_data.get("expected_answer_elements", []),
                                coverageRule=coverage_rule,
                            )
                            card = question_card_service.create_question_card(
                                db=db,
                                document_id=document_id,
                                section_id=section.id,
                                section_number=section.section_number,
                                card_data=card_create,
                                created_by="ai"
                            )
                            total_cards += 1

                            # Send card created event
                            try:
                                event_service.publish_sync(document_id, {
                                    'type': 'CARD_CREATED',
                                    'card_id': card.id,
                                    'section_id': section.id,
                                    'progress': {
                                        'current_card': total_cards,
                                        'current_slide': section_index + 1,
                                        'total_slides': total_sections,
                                        'percentage': int((section_index + 1) / total_sections * 100)
                                    }
                                })
                            except Exception:
                                pass

                            logger.info(f"Created question card {card.id} for section {section.id}")

                        except Exception as card_error:
                            logger.error(
                                f"Failed to create question card for section {section.id}: {card_error}",
                                exc_info=True
                            )
                            continue

                # Commit any remaining changes for this section
                db.commit()

            except Exception as section_error:
                logger.error(
                    f"Failed to analyze section {section.id}: {section_error}",
                    exc_info=True
                )
                continue

        # 4. Update document status to analyzed and prep session to ready
        document.status = "analyzed"
        document.updated_at = datetime.utcnow()
        db.commit()

        # Update associated prep session to ready
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
            f"Generated {total_cards} question cards across {total_sections} sections"
        )

        # Send completion event
        try:
            event_service.publish_sync(document_id, {
                'type': 'ANALYSIS_COMPLETE',
                'document_id': document_id,
                'total_cards': total_cards,
                'total_sections': total_sections,
            })
        except Exception as evt_err:
            logger.warning(f"Failed to publish analysis complete event: {evt_err}")

        return {
            "status": "success",
            "document_id": document_id,
            "total_sections": total_sections,
            "total_cards": total_cards,
        }

    except Exception as e:
        logger.error(f"Document analysis failed for {document_id}: {e}", exc_info=True)

        # Update document status to failed
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = "failed"
                db.commit()
        except Exception:
            pass

        # Retry if we haven't exceeded max retries
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
