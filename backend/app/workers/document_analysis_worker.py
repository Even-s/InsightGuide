"""Worker for AI-powered document analysis and question card generation."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from app.db.session import SessionLocal
from app.models.document import Document
from app.services.openai_service import openai_service
from app.services.s3_service import s3_service

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuideChunk:
    """A parsed portion of guide text used only during analysis."""

    chunk_number: int
    title: str
    text: str


def _snake_to_camel(name: str) -> str:
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


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
    1. Load document + guide text chunks
    2. Phase 1: Full-text analysis → generate InterviewThemes
    3. Phase 2: For each theme → generate QuestionCards
    4. Update document status
    """
    logger.info(f"Starting document analysis for document {document_id}")
    db = SessionLocal()

    try:
        import uuid

        from app.models.interview_theme import InterviewTheme
        from app.models.question_card import QuestionCard
        from app.services.event_service import event_service

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

        # 2. Extract guide chunks from file
        chunks = _extract_guide_chunks_from_file(document)
        if not chunks:
            document.status = "failed"
            db.commit()
            return {"status": "error", "message": "No guide content could be extracted"}

        logger.info(f"Found {len(chunks)} guide chunks for document {document_id}")

        # Build full document text for theme analysis
        full_text = "\n\n".join(
            f"## {chunk.title or f'Guide chunk {chunk.chunk_number}'}\n{chunk.text or ''}"
            for chunk in chunks
        )

        # 3. Phase 1: Generate interview themes from full document
        logger.info("Phase 1: Generating interview themes...")
        try:
            event_service.publish_sync(
                document_id,
                {
                    "type": "ANALYSIS_PROGRESS",
                    "message": "正在分析文件，產生訪談單元...",
                    "phase": "themes",
                },
            )
        except Exception:
            pass

        theme_result = openai_service.generate_interview_themes(
            document_title=document.title,
            full_text=full_text,
            guide_chunks=chunks,
            document_id=document_id,
        )

        # Save interview metadata to document
        document.interview_objective = theme_result.get("interview_objective", "")
        document.interview_priority_order = theme_result.get("priority_order", [])
        document.interview_priority_reasoning = theme_result.get("priority_reasoning", "")
        db.commit()

        # Create InterviewTheme records
        themes_data = theme_result.get("themes", [])
        created_themes = []

        for theme_data in themes_data:
            theme_id = f"theme_{uuid.uuid4().hex[:12]}"

            theme = InterviewTheme(
                id=theme_id,
                document_id=document_id,
                theme_number=theme_data.get("theme_number", 0),
                title=theme_data.get("title", "Untitled"),
                rationale=theme_data.get("rationale", ""),
                brd_mapping=theme_data.get("brd_mapping", []),
                priority=theme_data.get("priority", 99),
                estimated_minutes=theme_data.get("estimated_minutes"),
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
            event_service.publish_sync(
                document_id,
                {
                    "type": "THEMES_CREATED",
                    "theme_count": len(created_themes),
                },
            )
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
                    event_service.publish_sync(
                        document_id,
                        {
                            "type": "ANALYSIS_PROGRESS",
                            "message": f"正在為「{theme.title}」產生提問重點...",
                            "phase": "cards",
                            "current_theme": theme_index + 1,
                            "total_themes": total_themes,
                            "percentage": int((theme_index + 1) / total_themes * 100),
                        },
                    )
                except Exception:
                    pass

                source_guide_text = _select_guide_text_for_theme(
                    theme_data=themes_data[theme_index] if theme_index < len(themes_data) else {},
                    chunks=chunks,
                    full_text=full_text,
                )

                # Call OpenAI to generate cards for this theme
                cards_result = openai_service.generate_theme_question_cards(
                    document_title=document.title,
                    document_summary=document_summary,
                    theme_title=theme.title,
                    theme_rationale=theme.rationale,
                    theme_brd_mapping=theme.brd_mapping or [],
                    source_guide_text=source_guide_text,
                    document_id=document_id,
                )

                # Create QuestionCard records
                cards_data = cards_result.get("cards", [])
                created_cards = []

                for card_index, card_data in enumerate(cards_data):
                    try:
                        raw_importance = card_data.get("importance", "should")
                        importance = (
                            "must" if raw_importance in ("must", "high", "critical") else "should"
                        )

                        raw_coverage = card_data.get("coverage_rule")
                        coverage_rule = (
                            _convert_keys_to_camel(raw_coverage)
                            if raw_coverage
                            else {
                                "semanticAnchors": [],
                                "expectedKeywords": [],
                                "mustMentionElements": [],
                                "thresholds": {"probablySufficient": 0.65, "sufficient": 0.80},
                            }
                        )

                        card_id = f"qcard_{uuid.uuid4().hex[:12]}"
                        card = QuestionCard(
                            id=card_id,
                            document_id=document_id,
                            interview_theme_id=theme.id,
                            focus_text=card_data.get("focus_text", ""),
                            question_text=(card_data.get("question_text", "") or "")[:200]
                            or "Untitled",
                            question_type=card_data.get("question_type", "clarification"),
                            importance=importance,
                            coverage_rule=coverage_rule,
                            suggested_followup=card_data.get("suggested_followup", ""),
                            expected_answer_elements=card_data.get("expected_answer_elements", []),
                            brd_mapping=card_data.get("brd_mapping", []),
                            estimated_seconds=90,
                            order_index=card_index,
                            status="pending",
                            ui={
                                "color": "default",
                                "isVisible": True,
                                "isPinned": False,
                                "displayMode": "full",
                            },
                            created_by="ai",
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                        )
                        db.add(card)
                        created_cards.append(card)
                        total_cards += 1

                    except Exception as card_err:
                        logger.error(
                            f"Failed to create card for theme {theme.id}: {card_err}", exc_info=True
                        )
                        continue

                # Compile rubrics immediately (local, fast — no LLM)
                from app.services.question_rubric_service import question_rubric_service

                for card in created_cards:
                    try:
                        question_rubric_service.compile_and_save_rubric(db, card)
                    except Exception as e:
                        logger.warning(f"Failed to compile rubric for card {card.id}: {e}")

                db.commit()
                logger.info(f"Created {len(cards_data)} cards for theme {theme.title}")

                try:
                    event_service.publish_sync(
                        document_id,
                        {
                            "type": "THEME_CARDS_CREATED",
                            "theme_id": theme.id,
                            "theme_title": theme.title,
                            "card_count": len(cards_data),
                            "total_cards": total_cards,
                        },
                    )
                except Exception:
                    pass

            except Exception as theme_err:
                logger.error(
                    f"Failed to generate cards for theme {theme.id}: {theme_err}", exc_info=True
                )
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
            event_service.publish_sync(
                document_id,
                {
                    "type": "ANALYSIS_COMPLETE",
                    "document_id": document_id,
                    "total_themes": len(created_themes),
                    "total_cards": total_cards,
                },
            )
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


def _extract_guide_chunks_from_file(document: Document) -> list[GuideChunk]:
    """Download guide text and parse it into in-memory chunks."""
    try:
        object_key = (
            document.source_file_url.split("/insightguide-uploads/")[-1]
            if "insightguide-uploads/" in document.source_file_url
            else document.source_file_url
        )
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

    chunks_data = _parse_markdown_guide_chunks(text)

    if not chunks_data:
        chunks_data = [{"title": document.title or "Guide Content", "text": text.strip()}]

    chunks = [
        GuideChunk(chunk_number=idx, title=chunk["title"], text=chunk["text"])
        for idx, chunk in enumerate(chunks_data, start=1)
    ]
    logger.info(f"Parsed {len(chunks)} guide chunks for document {document.id}")
    return chunks


def _parse_markdown_guide_chunks(text: str) -> list:
    """Parse markdown text into guide chunks based on headings."""
    lines = text.split("\n")
    chunks = []
    current_title = None
    current_lines = []

    for line in lines:
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_match:
            if current_title and current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    chunks.append({"title": current_title, "text": content})
            current_title = heading_match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_title and current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            chunks.append({"title": current_title, "text": content})

    if not chunks and current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            chunks.append({"title": "Guide Content", "text": content})

    return chunks


def _select_guide_text_for_theme(theme_data: dict, chunks: list[GuideChunk], full_text: str) -> str:
    """Select source guide text for a generated theme without persisting source chunks."""
    chunk_numbers = theme_data.get("source_chunk_numbers", [])
    chunk_map = {chunk.chunk_number: chunk for chunk in chunks}
    selected = [
        f"### {chunk.title}\n{chunk.text}"
        for number in chunk_numbers
        if (chunk := chunk_map.get(number))
    ]
    return "\n\n".join(selected) if selected else full_text[:4000]
