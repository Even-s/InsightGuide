"""Diarization service using GPT-4o-transcribe with speaker identification."""

import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)


@dataclass
class DiarizedSegment:
    speaker: str  # "speaker_0", "speaker_1", etc.
    text: str
    start: float  # seconds from chunk start
    end: float


class DiarizeService:
    """Transcribes audio chunks with speaker diarization."""

    def __init__(self):
        self.model = "gpt-4o-transcribe"
        self.speaker_map: dict = {}  # Maps model speaker IDs to roles

    async def transcribe_chunk(
        self,
        audio_bytes: bytes,
        session_id: str,
        chunk_index: int,
        filename: str = "session_audio.webm",
        content_type: str = "audio/webm",
        db: Optional[Session] = None,
        document_id: Optional[str] = None,
    ) -> List[DiarizedSegment]:
        """Transcribe an audio chunk with diarization.

        Args:
            audio_bytes: Encoded audio bytes uploaded by the browser.
            session_id: For speaker mapping continuity and billing
            chunk_index: Sequential chunk number
            filename: Original upload filename
            content_type: Original upload MIME type
            db: Database session for billing tracking (optional)
            document_id: Document ID for billing (optional)
        """
        if len(audio_bytes) < 1600:
            return []

        try:
            # Use centralized OpenAI wrapper for billing and retry logic
            response = openai_service.audio_transcription(
                audio_bytes=audio_bytes,
                model=self.model,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                db=db,
                session_id=session_id,
                document_id=document_id,
                purpose="diarization",
            )

            segments = []
            if hasattr(response, "segments") and response.segments:
                for seg in response.segments:
                    speaker = getattr(seg, "speaker", None) or "speaker_0"
                    segments.append(
                        DiarizedSegment(
                            speaker=speaker,
                            text=seg.text.strip(),
                            start=seg.start,
                            end=seg.end,
                        )
                    )

            if not segments and hasattr(response, "text") and response.text.strip():
                segments.append(
                    DiarizedSegment(
                        speaker="speaker_0",
                        text=response.text.strip(),
                        start=0.0,
                        end=0.0,
                    )
                )

            return segments

        except Exception as e:
            logger.error(
                f"Diarize transcription failed for session {session_id} chunk {chunk_index}: {e}"
            )
            return []


diarize_service = DiarizeService()
