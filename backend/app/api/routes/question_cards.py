"""Question card management routes."""

import logging
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.question_card import (
    CardUI,
    CoverageRule,
    QuestionCardCreate,
    QuestionCardFollowupCleanupRequest,
    QuestionCardFollowupCleanupResponse,
    QuestionCardSchema,
    QuestionCardUpdate,
    SufficiencyEvidence,
)
from app.services.question_card_service import question_card_service
from app.services.semantic_judge_service import semantic_judge_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_document_editable(db: Session, document_id: str) -> None:
    """Reject every mutation against a guide that has entered interview history."""
    from app.models.document import Document

    document = db.query(Document).filter(Document.id == document_id).first()
    if document and document.is_frozen:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This interview guide is frozen. Create a new interview round to make changes.",
        )


def _ensure_card_editable(db: Session, question_card_id: str):
    card = question_card_service.get_question_card(db, question_card_id)
    _ensure_document_editable(db, card.document_id)
    return card


def convert_card_to_schema(card) -> QuestionCardSchema:
    """Convert a QuestionCard model instance to schema."""
    # Parse coverage rule
    normalized_rule = question_card_service.normalize_coverage_rule_for_important_elements(
        card.coverage_rule
    )
    coverage_rule = CoverageRule(**normalized_rule)

    # Parse evidence if exists
    evidence = None
    if hasattr(card, "evidence") and card.evidence:
        evidence = SufficiencyEvidence(**card.evidence)

    # Parse UI settings
    ui = None
    if card.ui:
        ui = CardUI(**card.ui)

    return QuestionCardSchema(
        id=card.id,
        documentId=card.document_id,
        interviewThemeId=card.interview_theme_id,
        sectionId=card.section_id,
        sectionNumber=card.section_number,
        focusText=card.focus_text,
        questionText=card.question_text,
        questionType=card.question_type,
        importance=card.importance,
        coverageRule=coverage_rule,
        suggestedFollowup=card.suggested_followup,
        expectedAnswerElements=card.expected_answer_elements or [],
        estimatedSeconds=card.estimated_seconds or 30,
        orderIndex=card.order_index,
        status=card.status,
        confidence=float(card.confidence) if card.confidence else None,
        evidence=evidence,
        ui=ui,
        targetRoles=card.target_roles,
        notRecommendedRoles=card.not_recommended_roles,
        expertiseRequired=card.expertise_required,
        questionIntent=card.question_intent,
        createdBy=card.created_by,
        createdAt=card.created_at,
        updatedAt=card.updated_at,
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=QuestionCardSchema)
async def create_question_card(question_card: QuestionCardCreate, db: Session = Depends(get_db)):
    """Create a new question card (user-created)."""
    from app.models.interview_theme import InterviewTheme

    section_id = question_card.resolved_section_id
    logger.info(f"Creating question card for section {section_id}")

    # Check if sectionId is actually an interview theme ID
    theme = db.query(InterviewTheme).filter(InterviewTheme.id == section_id).first()
    if theme:
        _ensure_document_editable(db, theme.document_id)
        card = question_card_service.create_question_card(
            db=db,
            document_id=theme.document_id,
            section_id=section_id,
            section_number=0,
            card_data=question_card,
            created_by="user",
            interview_theme_id=theme.id,
        )
    else:
        from app.services.section_service import section_service

        section = section_service.get_section(db, section_id)
        _ensure_document_editable(db, section.document_id)
        card = question_card_service.create_question_card(
            db=db,
            document_id=section.document_id,
            section_id=section_id,
            section_number=section.section_number,
            card_data=question_card,
        )

    return convert_card_to_schema(card)


@router.post("/followup/cleanup", response_model=QuestionCardFollowupCleanupResponse)
async def cleanup_question_card_followup(
    request: QuestionCardFollowupCleanupRequest,
):
    """Clean speech-transcribed question card followup content with GPT-5.4-mini."""
    cleaned_text = semantic_judge_service.clean_spoken_script(request.text)
    return QuestionCardFollowupCleanupResponse(cleanedText=cleaned_text)


@router.get("/{question_card_id}", response_model=QuestionCardSchema)
async def get_question_card(question_card_id: str, db: Session = Depends(get_db)):
    """Get question card by ID."""
    logger.info(f"Retrieving question card {question_card_id}")
    card = question_card_service.get_question_card(db, question_card_id)
    return convert_card_to_schema(card)


@router.patch("/{question_card_id}", response_model=QuestionCardSchema)
async def update_question_card(
    question_card_id: str, update_data: QuestionCardUpdate, db: Session = Depends(get_db)
):
    """Update question card. This is used in Editor Mode for customization."""
    logger.info(f"Updating question card {question_card_id}")
    _ensure_card_editable(db, question_card_id)
    card = question_card_service.update_question_card(db, question_card_id, update_data)
    return convert_card_to_schema(card)


@router.post("/{question_card_id}/followup/regenerate", response_model=QuestionCardSchema)
async def regenerate_question_card_followup(question_card_id: str, db: Session = Depends(get_db)):
    """Regenerate the suggested followup for a single question card."""
    logger.info(f"Regenerating suggested followup for question card {question_card_id}")
    _ensure_card_editable(db, question_card_id)
    card = question_card_service.regenerate_question_card_followup(db, question_card_id)
    return convert_card_to_schema(card)


@router.delete("/{question_card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question_card(question_card_id: str, db: Session = Depends(get_db)):
    """Delete a question card."""
    logger.info(f"Deleting question card {question_card_id}")
    _ensure_card_editable(db, question_card_id)
    question_card_service.delete_question_card(db, question_card_id)
    return None


@router.get("/document/{document_id}", response_model=List[QuestionCardSchema])
async def get_document_question_cards(document_id: str, db: Session = Depends(get_db)):
    """Get all question cards for a document."""
    logger.info(f"Retrieving question cards for document {document_id}")
    cards = question_card_service.get_question_cards_by_document(db, document_id)
    return [convert_card_to_schema(card) for card in cards]


@router.patch("/sections/{section_id}/reorder", response_model=List[QuestionCardSchema])
async def reorder_question_cards(
    section_id: str,
    card_order: List[str] = Body(..., description="Ordered list of question card IDs"),
    db: Session = Depends(get_db),
):
    """Reorder question cards for a section."""
    logger.info(f"Reordering {len(card_order)} question cards for section {section_id}")
    for card_id in card_order:
        _ensure_card_editable(db, card_id)
    cards = question_card_service.reorder_question_cards(db, section_id, card_order)
    return [convert_card_to_schema(card) for card in cards]


@router.post("/{question_card_id}/generate-criteria")
async def generate_criteria(question_card_id: str, db: Session = Depends(get_db)):
    """Generate evaluation criteria for a question card using AI. Returns without saving."""
    from app.services.question_rubric_service import question_rubric_service

    card = question_card_service.get_question_card(db, question_card_id)
    rubric = question_rubric_service.generate_rubric_with_llm(card)
    return {"criteria": rubric.get("criteria", [])}


@router.post("/{card_id}/generate-role-targeting")
async def generate_role_targeting(card_id: str, db: Session = Depends(get_db)):
    """Generate role targeting metadata for a question card using AI."""
    from app.models.question_card import QuestionCard
    from app.services.ai_question_generator import ai_question_generator

    card = db.query(QuestionCard).filter(QuestionCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    _ensure_document_editable(db, card.document_id)

    targeting = ai_question_generator.generate_role_targeting(
        question_text=card.question_text,
        question_type=card.question_type,
        section_context=card.focus_text or "",
    )

    card.target_roles = targeting["target_roles"]
    card.not_recommended_roles = targeting["not_recommended_roles"]
    card.expertise_required = targeting["expertise_required"]
    card.question_intent = targeting["question_intent"]
    db.commit()

    return targeting


@router.post("/document/{document_id}/generate-all-role-targeting")
async def generate_all_role_targeting(document_id: str, db: Session = Depends(get_db)):
    """Generate role targeting for all cards in a document that don't have it yet."""
    from app.models.question_card import QuestionCard
    from app.services.ai_question_generator import ai_question_generator

    _ensure_document_editable(db, document_id)
    cards = (
        db.query(QuestionCard)
        .filter(
            QuestionCard.document_id == document_id,
            QuestionCard.target_roles == None,
        )
        .all()
    )

    results = []
    for card in cards:
        targeting = ai_question_generator.generate_role_targeting(
            question_text=card.question_text,
            question_type=card.question_type,
            section_context=card.focus_text or "",
        )
        card.target_roles = targeting["target_roles"]
        card.not_recommended_roles = targeting["not_recommended_roles"]
        card.expertise_required = targeting["expertise_required"]
        card.question_intent = targeting["question_intent"]
        results.append({"card_id": card.id, **targeting})

    db.commit()
    return {"updated": len(results), "cards": results}
