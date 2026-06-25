"""BRD structured requirements extraction service.

Used by: /api/brd/generate (BRDGenerationPage)
Purpose: Extracts individual Requirement records from interview data using
structured AI output. Produces editable requirements with priorities/categories.

See also: brd_generation_service.py — evidence-based BRD + transcript/Q&A report
used by InterviewReportPage and project-level BRD generation.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.brd import BRDDraft, BRDStatus, Requirement, RequirementPriority, RequirementType
from app.models.interview_session import InterviewCardState, InterviewSession
from app.models.utterance import Utterance
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)


class BRDGeneratorService:
    """Generate business requirements documents from interview sessions."""

    def generate_brd(self, db: Session, session_id: str) -> BRDDraft:
        """
        Generate a complete BRD from a finished interview session.

        Args:
            db: Database session
            session_id: Interview session ID

        Returns:
            BRD Draft with generated content
        """
        start_time = datetime.utcnow()

        # Get interview session with all related data
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()

        if not session:
            raise ValueError(f"Interview session {session_id} not found")

        if session.status not in ["ended", "paused"]:
            raise ValueError(
                f"Interview session must be ended or paused to generate BRD. Current status: {session.status}"
            )

        # Check if BRD already exists
        existing_brd = (
            db.query(BRDDraft).filter(BRDDraft.interview_session_id == session_id).first()
        )

        if existing_brd:
            logger.info(f"BRD already exists for session {session_id}, regenerating...")
            brd_draft = existing_brd
            brd_draft.status = BRDStatus.GENERATING
            brd_draft.error_message = None
        else:
            # Create new BRD draft
            brd_draft = BRDDraft(
                id=f"brd_{uuid.uuid4().hex[:12]}",
                interview_session_id=session_id,
                user_id=session.user_id,
                status=BRDStatus.GENERATING,
            )
            db.add(brd_draft)

        db.commit()

        try:
            # Extract interview data
            interview_data = self._extract_interview_data(db, session)

            # Generate BRD sections using AI
            brd_content = self._generate_brd_content(interview_data)

            # Update BRD draft with generated content
            brd_draft.title = brd_content["title"]
            brd_draft.executive_summary = brd_content["executive_summary"]
            brd_draft.project_overview = brd_content["project_overview"]
            brd_draft.business_objectives = brd_content["business_objectives"]
            brd_draft.success_criteria = brd_content["success_criteria"]
            brd_draft.stakeholders = brd_content["stakeholders"]
            brd_draft.assumptions = brd_content["assumptions"]
            brd_draft.constraints = brd_content["constraints"]
            brd_draft.risks = brd_content["risks"]

            # Extract requirements and create Requirement records
            requirements_data = self._extract_requirements(db, interview_data)
            self._create_requirements(db, brd_draft.id, requirements_data)

            # Generate markdown representation
            brd_draft.markdown_content = self._generate_markdown(brd_draft, requirements_data)

            # Mark as completed
            end_time = datetime.utcnow()
            brd_draft.status = BRDStatus.COMPLETED
            brd_draft.generated_at = end_time
            brd_draft.generation_duration_seconds = str(
                int((end_time - start_time).total_seconds())
            )

            db.commit()
            logger.info(f"Successfully generated BRD for session {session_id}")

            return brd_draft

        except Exception as e:
            logger.error(f"Failed to generate BRD for session {session_id}: {e}", exc_info=True)
            brd_draft.status = BRDStatus.FAILED
            brd_draft.error_message = str(e)
            db.commit()
            raise

    def _extract_interview_data(self, db: Session, session: InterviewSession) -> Dict[str, Any]:
        """Extract all relevant data from interview session."""

        # Get document and sections
        document = session.document

        # Get all question cards with their states
        card_states = (
            db.query(InterviewCardState).filter(InterviewCardState.session_id == session.id).all()
        )

        questions_with_answers = []
        for state in card_states:
            card = state.question_card
            questions_with_answers.append(
                {
                    "card_id": card.id,
                    "question": card.question_text,
                    "importance": card.importance,
                    "status": state.status,
                    "confidence": float(state.confidence) if state.confidence else 0.0,
                    "answered": state.status in ["sufficient", "probably_sufficient"],
                    "evidence": state.evidence_transcript or "",
                    "section_number": card.section_number,
                }
            )

        # Get all utterances
        utterances = (
            db.query(Utterance)
            .filter(Utterance.session_id == session.id)
            .order_by(Utterance.created_at)
            .all()
        )

        full_transcript = "\n".join(
            [f"[{u.created_at.strftime('%H:%M:%S')}] {u.transcript}" for u in utterances]
        )

        return {
            "session_id": session.id,
            "document_title": document.title,
            "questions_with_answers": questions_with_answers,
            "full_transcript": full_transcript,
            "utterances": utterances,
            "total_questions": len(questions_with_answers),
            "answered_questions": len([q for q in questions_with_answers if q["answered"]]),
        }

    def _generate_brd_content(self, interview_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate BRD content sections using AI."""

        prompt = f"""You are a business analyst generating a Business Requirements Document (BRD) from an interview session.

Interview Context:
- Document: {interview_data['document_title']}
- Questions Asked: {interview_data['total_questions']}
- Questions Answered: {interview_data['answered_questions']}

Full Interview Transcript:
{interview_data['full_transcript'][:10000]}

Based on this interview, generate a comprehensive BRD with the following sections:

1. Title: A concise project title
2. Executive Summary: 2-3 paragraph overview
3. Project Overview: Detailed description of the project scope and context
4. Business Objectives: List of 3-5 key objectives
5. Success Criteria: List of measurable success criteria
6. Stakeholders: List of identified stakeholders
7. Assumptions: List of assumptions made
8. Constraints: List of constraints and limitations
9. Risks: List of potential risks

Return your response as a JSON object with these fields."""

        try:
            response = openai_service.generate_structured_output(
                prompt=prompt,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "brd_content",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "executive_summary": {"type": "string"},
                                "project_overview": {"type": "string"},
                                "business_objectives": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "success_criteria": {"type": "array", "items": {"type": "string"}},
                                "stakeholders": {"type": "array", "items": {"type": "string"}},
                                "assumptions": {"type": "array", "items": {"type": "string"}},
                                "constraints": {"type": "array", "items": {"type": "string"}},
                                "risks": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": [
                                "title",
                                "executive_summary",
                                "project_overview",
                                "business_objectives",
                                "success_criteria",
                                "stakeholders",
                                "assumptions",
                                "constraints",
                                "risks",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
            )
            return response
        except Exception as e:
            logger.error(f"Failed to generate BRD content: {e}")
            # Return default structure
            return {
                "title": interview_data["document_title"],
                "executive_summary": "Executive summary generation failed.",
                "project_overview": "Project overview generation failed.",
                "business_objectives": [],
                "success_criteria": [],
                "stakeholders": [],
                "assumptions": [],
                "constraints": [],
                "risks": [],
            }

    def _extract_requirements(
        self, db: Session, interview_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract individual requirements from interview answers."""

        requirements = []

        for qa in interview_data["questions_with_answers"]:
            if not qa["answered"] or not qa["evidence"]:
                continue

            prompt = f"""Extract functional and non-functional requirements from this interview question and answer.

Question: {qa['question']}
Answer Evidence: {qa['evidence']}

For each requirement, provide:
1. Title: Brief requirement title
2. Description: Detailed description
3. Type: functional, non_functional, business, user, or technical
4. Priority: must_have, should_have, or nice_to_have
5. User Story: As a [user], I want [feature], so that [benefit]
6. Acceptance Criteria: List of criteria

Return a JSON array of requirements."""

            try:
                response = openai_service.generate_structured_output(
                    prompt=prompt,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "requirements_extraction",
                            "strict": True,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "requirements": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "title": {"type": "string"},
                                                "description": {"type": "string"},
                                                "type": {
                                                    "type": "string",
                                                    "enum": [
                                                        "functional",
                                                        "non_functional",
                                                        "business",
                                                        "user",
                                                        "technical",
                                                    ],
                                                },
                                                "priority": {
                                                    "type": "string",
                                                    "enum": [
                                                        "must_have",
                                                        "should_have",
                                                        "nice_to_have",
                                                    ],
                                                },
                                                "user_story": {"type": "string"},
                                                "acceptance_criteria": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                            "required": [
                                                "title",
                                                "description",
                                                "type",
                                                "priority",
                                                "user_story",
                                                "acceptance_criteria",
                                            ],
                                            "additionalProperties": False,
                                        },
                                    }
                                },
                                "required": ["requirements"],
                                "additionalProperties": False,
                            },
                        },
                    },
                )

                for req in response.get("requirements", []):
                    req["source_question_card_id"] = qa["card_id"]
                    req["confidence"] = str(qa["confidence"])
                    requirements.append(req)

            except Exception as e:
                logger.error(f"Failed to extract requirements from question {qa['card_id']}: {e}")
                continue

        return requirements

    def _create_requirements(
        self, db: Session, brd_draft_id: str, requirements_data: List[Dict[str, Any]]
    ):
        """Create Requirement records in database."""

        for req_data in requirements_data:
            requirement = Requirement(
                id=f"req_{uuid.uuid4().hex[:12]}",
                brd_draft_id=brd_draft_id,
                title=req_data["title"],
                description=req_data["description"],
                type=RequirementType[req_data["type"].upper()],
                priority=RequirementPriority[req_data["priority"].upper()],
                source_question_card_id=req_data.get("source_question_card_id"),
                confidence=req_data.get("confidence"),
                user_story=req_data.get("user_story"),
                acceptance_criteria=req_data.get("acceptance_criteria"),
            )
            db.add(requirement)

        db.commit()

    def _generate_markdown(
        self, brd_draft: BRDDraft, requirements_data: List[Dict[str, Any]]
    ) -> str:
        """Generate markdown representation of BRD."""

        md = f"""# {brd_draft.title}

## Executive Summary

{brd_draft.executive_summary}

## Project Overview

{brd_draft.project_overview}

## Business Objectives

"""
        for obj in brd_draft.business_objectives or []:
            md += f"- {obj}\n"

        md += "\n## Success Criteria\n\n"
        for criteria in brd_draft.success_criteria or []:
            md += f"- {criteria}\n"

        md += "\n## Stakeholders\n\n"
        for stakeholder in brd_draft.stakeholders or []:
            md += f"- {stakeholder}\n"

        md += "\n## Assumptions\n\n"
        for assumption in brd_draft.assumptions or []:
            md += f"- {assumption}\n"

        md += "\n## Constraints\n\n"
        for constraint in brd_draft.constraints or []:
            md += f"- {constraint}\n"

        md += "\n## Risks\n\n"
        for risk in brd_draft.risks or []:
            md += f"- {risk}\n"

        md += "\n## Requirements\n\n"

        # Group requirements by type
        by_type: Dict[str, List[Dict]] = {}
        for req in requirements_data:
            req_type = req["type"]
            if req_type not in by_type:
                by_type[req_type] = []
            by_type[req_type].append(req)

        for req_type, reqs in by_type.items():
            md += f"\n### {req_type.replace('_', ' ').title()} Requirements\n\n"
            for req in reqs:
                md += f"#### {req['title']}\n\n"
                md += f"**Priority**: {req['priority'].replace('_', ' ').title()}\n\n"
                md += f"{req['description']}\n\n"
                md += f"**User Story**: {req['user_story']}\n\n"
                md += "**Acceptance Criteria**:\n\n"
                for criteria in req.get("acceptance_criteria", []):
                    md += f"- {criteria}\n"
                md += "\n"

        md += f"\n---\n\n*Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*\n"

        return md


brd_generator_service = BRDGeneratorService()
