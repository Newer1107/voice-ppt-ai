"""Pipeline orchestrator — coordinates all 8 processing stages.

Each stage is independently tested. The orchestrator:
1. Runs stages sequentially (each depends on previous output)
2. Updates job progress after each completed stage
3. Handles errors at each stage with proper rollback
4. Logs all failures and structured errors
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.src.config.settings import get_settings
from backend.src.infrastructure.db.models.lecture import LectureModel
from backend.src.infrastructure.db.models.job import JobModel
from backend.src.infrastructure.db.models.slide import SlideModel
from backend.src.infrastructure.db.models.narration import NarrationModel as NarrationDbModel
from backend.src.infrastructure.db.models.transcript_segment import TranscriptSegmentModel
from backend.src.infrastructure.db.models.file_record import FileModel
from backend.src.infrastructure.db.repositories.lecture_repo import LectureRepository
from backend.src.infrastructure.db.repositories.job_repo import JobRepository
from backend.src.infrastructure.db.repositories.slide_repo import SlideRepository
from backend.src.infrastructure.storage.local_storage import StoragePaths

from backend.src.worker.pipeline.extract_audio import extract_audio
from backend.src.worker.pipeline.transcribe import transcribe_audio
from backend.src.worker.pipeline.parse_pptx import parse_pptx
from backend.src.worker.pipeline.generate_embeddings import generate_embeddings
from backend.src.worker.pipeline.align_transcript import align_transcript
from backend.src.worker.pipeline.generate_narration import generate_narrations
from backend.src.worker.pipeline.generate_tts import generate_slide_tts
from backend.src.worker.pipeline.embed_narration import embed_narration_into_pptx

logger = logging.getLogger(__name__)

STAGE_WEIGHTS = {
    "extract_audio": 0.10,
    "transcribe": 0.25,
    "parse_pptx": 0.10,
    "generate_embeddings": 0.05,
    "align_transcript": 0.15,
    "generate_narration": 0.15,
    "generate_tts": 0.15,
    "embed_narration": 0.05,
}

STAGE_ORDER = [
    "extract_audio",
    "transcribe",
    "parse_pptx",
    "generate_embeddings",
    "align_transcript",
    "generate_narration",
    "generate_tts",
    "embed_narration",
]


def _update_progress(
    session,
    lecture_id: uuid.UUID,
    completed_stages: list[str],
) -> float:
    """Compute and persist overall pipeline progress."""
    progress = sum(STAGE_WEIGHTS[s] for s in completed_stages)
    repo = LectureRepository(session)
    repo.update_status(lecture_id, "processing" if progress < 1.0 else "completed")
    return min(progress, 1.0)


def _update_job_stage(
    session,
    lecture_id: uuid.UUID,
    stage: str,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Create or update job record for a pipeline stage."""
    repo = JobRepository(session)
    jobs = repo.list_by_lecture(lecture_id)
    job = next((j for j in jobs if j.job_type == stage), None)
    if job:
        job.status = status
        job.error_message = error_message
        if status == "running":
            job.started_at = datetime.now(timezone.utc)
        if status in ("completed", "failed"):
            job.completed_at = datetime.now(timezone.utc)
    else:
        job = JobModel(
            lecture_id=lecture_id,
            job_type=stage,
            status=status,
            error_message=error_message,
        )
        session.add(job)
    session.flush()


def run_full_pipeline(
    session,
    lecture_id: uuid.UUID,
    settings,
) -> None:
    """Execute the complete processing pipeline for a lecture.

    Called by the Celery task. All database operations use the
    provided session. All stages are sequential.
    """
    completed_stages = []
    lecture = None

    try:
        # Load lecture
        repo = LectureRepository(session)
        lecture = repo.get(lecture_id)
        if not lecture:
            raise ValueError(f"Lecture not found: {lecture_id}")

        lecture.status = "processing"
        session.flush()

        settings = get_settings()
        storage_root = Path(settings.STORAGE_ROOT)
        project_id = str(lecture.project_id)
        lid = str(lecture_id)

        # ─── Stage 1: Extract Audio ──────────────────────────────────
        logger.info("PIPELINE [%s]: Stage 1/8 — Extract Audio", lecture_id)
        _update_job_stage(session, lecture_id, "extract_audio", "running")

        if lecture.video_path and not lecture.audio_path:
            src_path = str(storage_root / lecture.video_path)
            rel_out = StoragePaths.extracted_audio(lid, project_id)
            abs_out = str(storage_root / rel_out)
            audio_result = extract_audio(src_path, abs_out)
            lecture.audio_path = rel_out
            lecture.duration_seconds = int(audio_result.duration_seconds)
        elif lecture.audio_path:
            audio_result = type('obj', (object,), {'duration_seconds': lecture.duration_seconds or 0})()
        else:
            raise ValueError("No video or audio available for extraction")

        _update_job_stage(session, lecture_id, "extract_audio", "completed")
        completed_stages.append("extract_audio")
        _update_progress(session, lecture_id, completed_stages)

        # ─── Stage 2: Transcribe ─────────────────────────────────────
        logger.info("PIPELINE [%s]: Stage 2/8 — Transcribe", lecture_id)
        _update_job_stage(session, lecture_id, "transcribe", "running")

        audio_abs = str(storage_root / lecture.audio_path) if lecture.audio_path else None
        if not audio_abs or not os.path.exists(audio_abs):
            raise FileNotFoundError(f"Audio file not found: {audio_abs}")

        transcript = transcribe_audio(audio_abs)

        # Store transcript segments in DB
        for seg in transcript.segments:
            ts = TranscriptSegmentModel(
                lecture_id=lecture_id,
                segment_number=seg.segment_number,
                start_time=seg.start_time,
                end_time=seg.end_time,
                text=seg.text,
                confidence=seg.confidence,
            )
            session.add(ts)
        session.flush()

        _update_job_stage(session, lecture_id, "transcribe", "completed")
        completed_stages.append("transcribe")
        _update_progress(session, lecture_id, completed_stages)

        # ─── Stage 3: Parse PPTX ─────────────────────────────────────
        logger.info("PIPELINE [%s]: Stage 3/8 — Parse PPTX", lecture_id)
        _update_job_stage(session, lecture_id, "parse_pptx", "running")

        slides_data = []
        if lecture.pptx_path:
            pptx_abs = str(storage_root / lecture.pptx_path)
            pptx_result = parse_pptx(pptx_abs)

            for ps in pptx_result.slides:
                sm = SlideModel(
                    lecture_id=lecture_id,
                    slide_number=ps.slide_number,
                    raw_text=ps.raw_text,
                    notes=ps.notes,
                    slide_layout=ps.slide_layout,
                )
                session.add(sm)
                slides_data.append({
                    "slide_number": ps.slide_number,
                    "raw_text": ps.raw_text,
                    "notes": ps.notes,
                })
            session.flush()
        else:
            logger.info("No PPTX to parse for lecture %s", lecture_id)

        _update_job_stage(session, lecture_id, "parse_pptx", "completed")
        completed_stages.append("parse_pptx")
        _update_progress(session, lecture_id, completed_stages)

        # ─── Stage 4: Generate Embeddings ────────────────────────────
        logger.info("PIPELINE [%s]: Stage 4/8 — Generate Embeddings", lecture_id)
        _update_job_stage(session, lecture_id, "generate_embeddings", "running")

        if slides_data:
            slide_texts = [s["raw_text"] for s in slides_data if s["raw_text"].strip()]
            seg_texts = [seg.text for seg in transcript.segments if seg.text.strip()]

            all_texts = slide_texts + seg_texts
            if all_texts:
                generate_embeddings(all_texts)
                logger.info("Generated embeddings for %d texts", len(all_texts))

        _update_job_stage(session, lecture_id, "generate_embeddings", "completed")
        completed_stages.append("generate_embeddings")
        _update_progress(session, lecture_id, completed_stages)

        # ─── Stage 5: Align Transcript ───────────────────────────────
        logger.info("PIPELINE [%s]: Stage 5/8 — Align Transcript", lecture_id)
        _update_job_stage(session, lecture_id, "align_transcript", "running")

        if slides_data and transcript.segments:
            seg_dicts = [
                {"segment_number": s.segment_number, "start_time": s.start_time, "end_time": s.end_time, "text": s.text}
                for s in transcript.segments
            ]
            alignment = align_transcript(seg_dicts, slides_data)

            # Update DB with alignment
            for al in alignment.alignments:
                slide_num = al.slide_number
                slide = session.query(SlideModel).filter(
                    SlideModel.lecture_id == lecture_id,
                    SlideModel.slide_number == slide_num,
                ).first()
                if slide:
                    seg_ids = al.segment_numbers
                    for seg in transcript.segments:
                        if seg.segment_number in seg_ids:
                            ts = session.query(TranscriptSegmentModel).filter(
                                TranscriptSegmentModel.lecture_id == lecture_id,
                                TranscriptSegmentModel.segment_number == seg.segment_number,
                            ).first()
                            if ts:
                                ts.slide_id = slide.id
            session.flush()
            logger.info("Aligned %d segments to %d slides", len(seg_dicts), len(slides_data))
        else:
            logger.info("No alignment needed (missing slides or transcript)")

        _update_job_stage(session, lecture_id, "align_transcript", "completed")
        completed_stages.append("align_transcript")
        _update_progress(session, lecture_id, completed_stages)

        # ─── Stage 6: Generate Narration ─────────────────────────────
        logger.info("PIPELINE [%s]: Stage 6/8 — Generate Narration", lecture_id)
        _update_job_stage(session, lecture_id, "generate_narration", "running")

        if slides_data:
            slides_with_transcripts = []
            for s in slides_data:
                sn = s["slide_number"]
                slide = session.query(SlideModel).filter(
                    SlideModel.lecture_id == lecture_id,
                    SlideModel.slide_number == sn,
                ).first()
                segs_for_slide = []
                if slide:
                    segs = session.query(TranscriptSegmentModel).filter(
                        TranscriptSegmentModel.slide_id == slide.id,
                    ).order_by(TranscriptSegmentModel.segment_number).all()
                    segs_for_slide = [
                        {"start_time": ts.start_time, "end_time": ts.end_time, "text": ts.text}
                        for ts in segs
                    ]
                slides_with_transcripts.append({
                    "slide_number": sn,
                    "raw_text": s["raw_text"],
                    "notes": s["notes"],
                    "transcript_segments": segs_for_slide,
                })

            narrations = generate_narrations(lecture.title, slides_with_transcripts)

            # Store narrations in DB
            for nr in narrations:
                slide = session.query(SlideModel).filter(
                    SlideModel.lecture_id == lecture_id,
                    SlideModel.slide_number == nr.slide_number,
                ).first()
                if slide:
                    narration_db = NarrationDbModel(
                        slide_id=slide.id,
                        lecture_id=lecture_id,
                        script_text=nr.script_text,
                        status="completed",
                        duration_seconds=float(nr.estimated_duration_seconds),
                    )
                    session.add(narration_db)
            session.flush()

        _update_job_stage(session, lecture_id, "generate_narration", "completed")
        completed_stages.append("generate_narration")
        _update_progress(session, lecture_id, completed_stages)

        # ─── Stage 7: Generate TTS ───────────────────────────────────
        logger.info("PIPELINE [%s]: Stage 7/8 — Generate TTS", lecture_id)
        _update_job_stage(session, lecture_id, "generate_tts", "running")

        narrations_db = session.query(NarrationDbModel).filter(
            NarrationDbModel.lecture_id == lecture_id,
        ).all()

        for ndb in narrations_db:
            slide = session.query(SlideModel).filter(
                SlideModel.id == ndb.slide_id,
            ).first()
            if not slide:
                continue

            rel_audio = StoragePaths.narration_audio(lid, project_id, slide.slide_number)
            abs_audio = str(storage_root / rel_audio)
            tts_result = generate_slide_tts(
                text=ndb.script_text,
                output_path=abs_audio,
                slide_number=slide.slide_number,
            )
            ndb.audio_path = rel_audio
            ndb.duration_seconds = tts_result.duration_seconds
        session.flush()

        _update_job_stage(session, lecture_id, "generate_tts", "completed")
        completed_stages.append("generate_tts")
        _update_progress(session, lecture_id, completed_stages)

        # ─── Stage 8: Embed Narration into PPTX ──────────────────────
        logger.info("PIPELINE [%s]: Stage 8/8 — Embed Narration", lecture_id)
        _update_job_stage(session, lecture_id, "embed_narration", "running")

        if lecture.pptx_path:
            pptx_abs = str(storage_root / lecture.pptx_path)
            slide_audio_map = {}
            for ndb in narrations_db:
                if ndb.audio_path:
                    slide = session.query(SlideModel).filter(
                        SlideModel.id == ndb.slide_id,
                    ).first()
                    if slide:
                        slide_audio_map[slide.slide_number] = str(storage_root / ndb.audio_path)

            if slide_audio_map:
                rel_out = StoragePaths.output_pptx(lid, project_id)
                abs_out = str(storage_root / rel_out)
                embed_result = embed_narration_into_pptx(
                    pptx_path=pptx_abs,
                    slide_audio_map=slide_audio_map,
                    output_path=abs_out,
                )
                lecture.narrated_pptx_path = embed_result.output_path
                session.flush()

        _update_job_stage(session, lecture_id, "embed_narration", "completed")
        completed_stages.append("embed_narration")

        # ─── Complete ─────────────────────────────────────────────────
        final_progress = _update_progress(session, lecture_id, completed_stages)
        lecture.status = "completed"
        session.flush()

        logger.info(
            "PIPELINE [%s]: Complete! Progress=%.0f%%",
            lecture_id, final_progress * 100,
        )

    except Exception as e:
        logger.exception("PIPELINE [%s]: Failed at stage %d/%d",
                          lecture_id, len(completed_stages) + 1, len(STAGE_ORDER))
        if lecture:
            lecture.status = "failed"
            lecture.error_message = str(e)
        if completed_stages:
            current_stage = STAGE_ORDER[len(completed_stages)] if len(completed_stages) < len(STAGE_ORDER) else "unknown"
            _update_job_stage(session, lecture_id, current_stage, "failed", str(e))
        session.flush()
        raise
