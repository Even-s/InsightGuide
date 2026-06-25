"""Realtime API integration routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.realtime_service import realtime_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/transcription-session")
async def create_realtime_transcription_session(db: Session = Depends(get_db)):
    """
    Create an ephemeral token for OpenAI Realtime transcription.

    The frontend connects to OpenAI directly with this token and streams
    microphone audio over WebRTC. InsightGuide receives completed transcript turns
    through the existing utterance endpoint.
    """
    logger.info("Creating Realtime transcription ephemeral token")

    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenAI API key not configured",
        )

    try:
        token_data = realtime_service.create_transcription_ephemeral_token()

        return {
            "token": token_data["token"],
            "transcriptionModel": token_data["transcriptionModel"],
            "expiresAt": token_data["expiresAt"],
            "sessionId": token_data["sessionId"],
        }

    except Exception as e:
        logger.error(f"Error creating Realtime transcription session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Realtime transcription session: {str(e)}",
        )
