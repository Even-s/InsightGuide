"""Diarization endpoint — post-interview batch processing for speaker identification.

Phase 1: Updated to write to final_utterances instead of replacing old utterances.
"""

import logging
import uuid
from datetime import datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.diarize_service import diarize_service
from app.services.s3_service import s3_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/diarize/{session_id}")
async def diarize_session_audio(
    session_id: str,
    audio: UploadFile = File(...),
    recording_started_at: str = Form(...),
    db: Session = Depends(get_db),
):
    """Post-interview: diarize the full session audio and create final transcript.

    Phase 1 Changes:
    - Creates a TranscriptRevision record
    - Writes segments to final_utterances (not utterances)
    - Does NOT delete live_utterances (they remain for debugging/traceability)
    - Updates session.transcript_status = 'finalized'
    """
    from app.models.final_utterance import FinalUtterance
    from app.models.interview_session import InterviewSession
    from app.models.transcript_revision import TranscriptRevision

    logger.info(f"Starting post-interview diarization for session {session_id}")

    # Verify session exists
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        rec_start = datetime.fromisoformat(recording_started_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recording_started_at timestamp")

    audio_bytes = await audio.read()
    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=400, detail="Audio file too short")

    # Create transcript revision record
    revision_id = f"rev_{uuid.uuid4().hex[:12]}"
    revision = TranscriptRevision(
        id=revision_id,
        session_id=session_id,
        source="diarized",
        model="gpt-4o-transcribe",
        status="processing",
        recording_started_at=rec_start,
        created_at=datetime.utcnow(),
    )
    db.add(revision)

    upload_filename = audio.filename or "session_audio.webm"
    file_ext = upload_filename.rsplit(".", 1)[-1].lower() if "." in upload_filename else "webm"
    content_type = audio.content_type or "audio/webm"

    # Save audio to local filesystem
    import os

    audio_dir = os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ),
        "uploads",
        "audio",
        session_id,
    )
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, f"{revision_id}.{file_ext}")

    try:
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)
        revision.audio_file_url = audio_path
        logger.info(f"Saved interview audio locally: {audio_path}")
    except Exception as e:
        logger.error(f"Failed to save interview audio for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save interview audio")

    # Update session status
    session.transcript_status = "diarizing"
    db.commit()

    try:
        # Perform diarization
        segments = await diarize_service.transcribe_chunk(
            audio_bytes=audio_bytes,
            session_id=session_id,
            chunk_index=0,
            filename=upload_filename,
            content_type=content_type,
        )

        if not segments:
            revision.status = "failed"
            revision.error_message = "No segments returned from diarization"
            session.transcript_status = "diarize_failed"
            db.commit()
            return {"status": "no_segments", "inserted": 0}

        # Insert diarized segments as final utterances
        rec_start_naive = rec_start.replace(tzinfo=None) if rec_start.tzinfo else rec_start
        inserted = 0

        for idx, seg in enumerate(segments):
            if not seg.text.strip():
                continue

            # Generate speaker display name (Speaker 1, Speaker 2, etc.)
            try:
                speaker_num = (
                    int(seg.speaker.split("_")[1]) + 1
                    if seg.speaker.startswith("speaker_")
                    else idx + 1
                )
                speaker_display_name = f"Speaker {speaker_num}"
            except (IndexError, ValueError):
                speaker_display_name = seg.speaker

            utt = FinalUtterance(
                id=f"futt_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                transcript_revision_id=revision_id,
                speaker_label=seg.speaker,
                speaker_display_name=speaker_display_name,
                transcript=seg.text.strip(),
                start_seconds=seg.start,
                end_seconds=seg.end,
                started_at=rec_start_naive + timedelta(seconds=seg.start),
                ended_at=rec_start_naive + timedelta(seconds=seg.end),
                sequence_index=idx,
                created_at=datetime.utcnow(),
            )
            db.add(utt)
            inserted += 1

        # Update revision and session status
        revision.status = "completed"
        revision.segment_count = inserted
        revision.completed_at = datetime.utcnow()
        session.transcript_status = "finalized"
        session.final_transcript_revision_id = revision_id

        db.commit()
        logger.info(
            f"Diarization complete: created {inserted} final utterances (live utterances preserved)"
        )

        # Phase 4: Run Q/A reconstruction
        try:
            from app.services.qa_reconstruction_service import qa_reconstruction_service

            logger.info(f"Running Q/A reconstruction for session {session_id}")
            qa_reconstruction_service.reconstruct(
                db=db,
                session_id=session_id,
                document_id=session.document_id,
            )
            logger.info(f"Q/A reconstruction complete for session {session_id}")
        except Exception as e:
            logger.error(f"Q/A reconstruction failed: {str(e)}", exc_info=True)
            # Don't fail the whole diarization if Q/A reconstruction fails

        # Phase 2: Run final card coverage evaluation
        try:
            from app.services.answer_evaluation_engine import answer_evaluation_engine

            logger.info(f"Running final card coverage evaluation for session {session_id}")
            final_results = answer_evaluation_engine.run_final_coverage(
                db=db,
                session_id=session_id,
                transcript_revision_id=revision_id,
            )
            logger.info(f"Final card coverage complete: {len(final_results)} cards evaluated")
            session.card_coverage_status = "finalized"
            db.commit()
        except Exception as e:
            logger.error(f"Final coverage evaluation failed: {str(e)}", exc_info=True)
            # Don't fail the whole diarization if final coverage fails
            session.card_coverage_status = "failed"
            db.commit()

        # Phase 5: Run utterance alignment
        try:
            from app.services.alignment_service import alignment_service

            logger.info(f"Running utterance alignment for session {session_id}")
            alignment_service.align(
                db=db,
                session_id=session_id,
                transcript_revision_id=revision_id,
            )
            logger.info(f"Utterance alignment complete for session {session_id}")
        except Exception as e:
            logger.error(f"Utterance alignment failed: {str(e)}", exc_info=True)
            # Don't fail the whole diarization if alignment fails

        return {
            "status": "completed",
            "revisionId": revision_id,
            "totalSegments": len(segments),
            "inserted": inserted,
            "speakers": list(set(s.speaker for s in segments)),
        }

    except Exception as e:
        logger.error(f"Diarization failed: {str(e)}", exc_info=True)
        revision.status = "failed"
        revision.error_message = str(e)
        session.transcript_status = "diarize_failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Diarization failed: {str(e)}")
