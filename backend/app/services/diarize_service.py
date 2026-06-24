"""Diarization service using GPT-4o-transcribe with speaker identification."""

import logging
import io
from typing import List
from dataclasses import dataclass
from openai import OpenAI

from app.core.config import settings

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
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30.0)
        self.model = "gpt-4o-transcribe"
        self.speaker_map: dict = {}  # Maps model speaker IDs to roles

    async def transcribe_chunk(
        self,
        audio_bytes: bytes,
        session_id: str,
        chunk_index: int,
        filename: str = "session_audio.webm",
        content_type: str = "audio/webm",
    ) -> List[DiarizedSegment]:
        """Transcribe an audio chunk with diarization.

        Args:
            audio_bytes: Encoded audio bytes uploaded by the browser.
            session_id: For speaker mapping continuity
            chunk_index: Sequential chunk number
            filename: Original upload filename
            content_type: Original upload MIME type
        """
        if len(audio_bytes) < 1600:
            return []

        try:
            upload_name = filename or "session_audio.webm"
            upload_type = content_type or "audio/webm"
            response = self.client.audio.transcriptions.create(
                model=self.model,
                file=(upload_name, io.BytesIO(audio_bytes), upload_type),
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                include=["logprobs"],
            )

            segments = []
            if hasattr(response, 'segments') and response.segments:
                for seg in response.segments:
                    speaker = getattr(seg, 'speaker', None) or "speaker_0"
                    segments.append(DiarizedSegment(
                        speaker=speaker,
                        text=seg.text.strip(),
                        start=seg.start,
                        end=seg.end,
                    ))

            if not segments and hasattr(response, 'text') and response.text.strip():
                segments.append(DiarizedSegment(
                    speaker="speaker_0",
                    text=response.text.strip(),
                    start=0.0,
                    end=0.0,
                ))

            return segments

        except Exception as e:
            logger.error(f"Diarize transcription failed for session {session_id} chunk {chunk_index}: {e}")
            return []


diarize_service = DiarizeService()
