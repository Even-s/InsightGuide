"""OpenAI Realtime API integration service."""

import logging
from typing import Dict, Any
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class RealtimeService:
    """Service for OpenAI Realtime transcription operations."""

    def __init__(self):
        """Initialize Realtime service."""
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = "https://api.openai.com/v1"

    def create_transcription_ephemeral_token(self) -> Dict[str, Any]:
        """
        Create an ephemeral client secret for Realtime transcription.

        The browser uses this short-lived token to stream microphone audio
        directly to OpenAI over WebRTC. Completed transcript turns are then
        sent back to InsightGuide as utterances for card matching.
        """
        try:
            logger.info("Creating ephemeral Realtime transcription token")

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            data = {
                "session": {
                    "type": "transcription",
                    "audio": {
                        "input": {
                            "noise_reduction": {"type": "near_field"},
                            "transcription": {
                                "model": settings.REALTIME_TRANSCRIPTION_MODEL,
                                "language": "zh",
                                "delay": "medium",
                            },
                        }
                    },
                }
            }

            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url}/realtime/client_secrets",
                    headers=headers,
                    json=data,
                )

                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(
                        f"Failed to create transcription token: {response.status_code} - {error_detail}"
                    )
                    raise Exception(f"OpenAI API error: {response.status_code} - {error_detail}")

                result = response.json()

            token = result.get("value")
            expires_at = result.get("expires_at")
            session_config = result.get("session", {})

            if not token:
                raise Exception("No token returned from OpenAI API")

            logger.info(f"Successfully created transcription token, expires at {expires_at}")

            return {
                "token": token,
                "transcriptionModel": settings.REALTIME_TRANSCRIPTION_MODEL,
                "expiresAt": expires_at,
                "sessionId": session_config.get("id"),
            }

        except Exception as e:
            logger.error(f"Error creating transcription token: {str(e)}")
            raise


# Singleton instance
realtime_service = RealtimeService()
