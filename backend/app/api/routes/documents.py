"""Document management routes."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import asyncio

from app.db.session import get_db
from app.services.document_service import document_service
from app.services.billing_service import billing_service
from app.services.s3_service import s3_service
from app.schemas.document import DocumentResponse, DocumentStatus, DocumentAnalysisResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def convert_document_to_response(document, db: Session) -> DocumentResponse:
    """Convert document model to API response with document-level AI usage."""
    # TODO: Implement billing service for documents
    usage = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0, "totalCostUsd": 0}
    return DocumentResponse(
        id=document.id,
        user_id=document.user_id,
        title=document.title,
        source_file_url=document.source_file_url,
        file_type=document.file_type,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        cost_usd=usage["totalCostUsd"],
        ai_usage=usage,
    )


def browser_safe_file_url(file_url: str | None) -> str | None:
    """Return a browser-accessible URL for private MinIO/S3 objects."""
    if not file_url:
        return None

    try:
        return s3_service.generate_presigned_url(file_url)
    except Exception as exc:
        logger.warning(f"Could not generate presigned URL for {file_url}: {exc}")
        return file_url.replace("http://minio:9000", "http://localhost:9000")


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=DocumentResponse)
async def create_document(
    file: UploadFile = File(..., description="PDF, Word, Markdown, or Text file to upload"),
    title: Optional[str] = Form(None, description="Optional document title"),
    db: Session = Depends(get_db)
):
    """
    Upload a requirements document and create a new document record.

    This endpoint:
    1. Validates the uploaded file (accepts .pdf, .docx, .doc, .md, .txt)
    2. Uploads it to S3 storage
    3. Creates a document record in the database
    4. Enqueues a background job for processing:
       - Extracts sections from the document
       - Analyzes content with AI
       - Generates question cards
    """
    logger.info(f"Creating document from file: {file.filename}")

    document = document_service.create_document(
        db=db,
        file=file,
        title=title
    )

    return convert_document_to_response(document, db)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get document by ID with current status."""
    logger.info(f"Retrieving document {document_id}")
    document = document_service.get_document(db, document_id)
    return convert_document_to_response(document, db)


@router.get("/{document_id}/status", response_model=DocumentStatus)
async def get_document_status(document_id: str, db: Session = Depends(get_db)):
    """Get document processing status."""
    document = document_service.get_document(db, document_id)
    # TODO: Implement billing service for documents
    usage = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0, "totalCostUsd": 0}

    status_messages = {
        "uploaded": "File uploaded, waiting for processing",
        "processing": "Processing file and extracting sections",
        "converted": "Processing complete, ready for AI analysis",
        "analyzing": "AI is analyzing sections and generating question cards",
        "analyzed": "Analysis complete, document is ready for editing",
        "failed": "Processing failed, please try again",
    }

    return DocumentStatus(
        id=document.id,
        status=document.status,
        message=status_messages.get(document.status, "Unknown status"),
        cost_usd=usage["totalCostUsd"],
        ai_usage=usage,
    )


@router.get("/{document_id}/analysis", response_model=DocumentAnalysisResponse)
async def get_document_analysis(document_id: str, db: Session = Depends(get_db)):
    """
    Get document analysis results including sections and question cards.

    This endpoint returns the complete analysis results after
    AI processing is complete.
    """
    from app.services.section_service import section_service
    from app.services.question_card_service import question_card_service
    from app.schemas.section import SectionWithQuestionCards
    from app.schemas.question_card import QuestionCardSchema

    document = document_service.get_document(db, document_id)

    if document.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document analysis failed. Please re-upload."
        )

    # Load sections
    sections = section_service.get_sections_by_document(db, document_id)

    # Load all question cards for the document
    all_question_cards = question_card_service.get_question_cards_by_document(db, document_id)
    # TODO: Implement billing service for documents
    usage = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0, "totalCostUsd": 0}

    # Build slides (sections) with question card counts
    slides_data = []
    for section in sections:
        section_cards = [c for c in all_question_cards if c.section_id == section.id]

        slides_data.append({
            "id": section.id,
            "deck_id": section.document_id,
            "page_number": section.section_number,
            "title": section.title,
            "extracted_text": section.extracted_text,
            "ai_summary": section.ai_summary,
            "topic_cards_count": len(section_cards)
        })

    return DocumentAnalysisResponse(
        document_id=document.id,
        status=document.status,
        slides=slides_data,
        topic_cards_count=len(all_question_cards),
        created_at=document.created_at,
        updated_at=document.updated_at,
        cost_usd=usage["totalCostUsd"],
        ai_usage=usage,
    )


@router.get("/{document_id}/interview-plan")
async def get_interview_plan(document_id: str, db: Session = Depends(get_db)):
    """Get the interview plan: themes + question cards grouped by theme."""
    from app.models.interview_theme import InterviewTheme
    from app.models.question_card import QuestionCard

    document = document_service.get_document(db, document_id)

    themes = db.query(InterviewTheme).filter(
        InterviewTheme.document_id == document_id
    ).order_by(InterviewTheme.order_index).all()

    all_cards = db.query(QuestionCard).filter(
        QuestionCard.document_id == document_id,
        QuestionCard.interview_theme_id.isnot(None)
    ).order_by(QuestionCard.order_index).all()

    cards_by_theme = {}
    for card in all_cards:
        cards_by_theme.setdefault(card.interview_theme_id, []).append(card)

    themes_data = []
    for theme in themes:
        theme_cards = cards_by_theme.get(theme.id, [])
        themes_data.append({
            "id": theme.id,
            "themeNumber": theme.theme_number,
            "title": theme.title,
            "rationale": theme.rationale,
            "brdMapping": theme.brd_mapping or [],
            "priority": theme.priority,
            "estimatedMinutes": theme.estimated_minutes,
            "sourceSectionIds": theme.source_section_ids or [],
            "orderIndex": theme.order_index,
            "isRequired": theme.is_required,
            "isEnabled": theme.is_enabled,
            "userNotes": theme.user_notes,
            "cards": [
                {
                    "id": c.id,
                    "focusText": c.focus_text,
                    "questionText": c.question_text,
                    "questionType": c.question_type,
                    "importance": c.importance,
                    "suggestedFollowup": c.suggested_followup,
                    "expectedAnswerElements": c.expected_answer_elements or [],
                    "brdMapping": c.brd_mapping or [],
                    "estimatedSeconds": c.estimated_seconds,
                    "orderIndex": c.order_index,
                    "status": c.status,
                    "confidence": float(c.confidence) if c.confidence else None,
                    "createdBy": c.created_by,
                }
                for c in theme_cards
            ],
        })

    return {
        "documentId": document.id,
        "status": document.status,
        "interviewObjective": document.interview_objective,
        "priorityOrder": document.interview_priority_order or [],
        "priorityReasoning": document.interview_priority_reasoning,
        "themes": themes_data,
        "totalCards": len(all_cards),
    }


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Delete a document and all associated files and data."""
    logger.info(f"Deleting document {document_id}")
    document_service.delete_document(db, document_id)
    return None


@router.get("/{document_id}/sections")
async def get_document_sections(document_id: str, db: Session = Depends(get_db)):
    """Get all sections for a document."""
    document = document_service.get_document(db, document_id)

    # TODO: Query sections from database
    # For now, return empty list
    return {
        "document_id": document.id,
        "sections": []
    }


@router.get("/{document_id}/events")
async def document_events_stream(document_id: str, db: Session = Depends(get_db)):
    """
    SSE endpoint for real-time document events (card generation progress).

    Events:
    - CARD_CREATED: New question card generated
    - ANALYSIS_COMPLETE: All sections analyzed
    """
    from app.services.event_service import event_service
    import redis.asyncio as async_redis
    from app.core.config import settings

    # Verify document exists
    document_service.get_document(db, document_id)

    async def event_generator():
        """Generate SSE events for this document."""
        queue = await event_service.subscribe(f"document_{document_id}")
        redis_client = async_redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(event_service.redis_channel(f"document_{document_id}"))

        try:
            # Send initial connected event
            yield f"event: connected\ndata: {{\"status\": \"connected\", \"document_id\": \"{document_id}\"}}\n\n"

            # Stream events from queue
            while True:
                try:
                    redis_message_task = asyncio.create_task(pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=30.0
                    ))
                    local_message_task = asyncio.create_task(queue.get())

                    done, pending = await asyncio.wait(
                        {redis_message_task, local_message_task},
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=30.0,
                    )

                    for task in pending:
                        task.cancel()

                    if not done:
                        yield ": keepalive\n\n"
                        continue

                    completed_task = done.pop()
                    message = completed_task.result()

                    if isinstance(message, dict):
                        event_data = message.get("data")
                    else:
                        event_data = message

                    if event_data:
                        yield event_data if str(event_data).endswith("\n\n") else f"{event_data}\n\n"

                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent connection timeout
                    yield ": keepalive\n\n"
                except Exception as e:
                    logger.error(f"Error in event generator: {e}")
                    break

        finally:
            await pubsub.unsubscribe(event_service.redis_channel(f"document_{document_id}"))
            await pubsub.close()
            await redis_client.close()
            await event_service.unsubscribe(f"document_{document_id}", queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        }
    )
