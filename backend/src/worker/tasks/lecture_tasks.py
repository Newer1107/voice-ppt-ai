"""Celery task definitions for the lecture processing pipeline."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config.settings import get_settings
from backend.src.infrastructure.db.session import async_session_maker
from backend.src.worker.celery_app import celery_app
from backend.src.worker.pipeline.orchestrator import run_full_pipeline

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, exponential_backoff=2, acks_late=True, reject_on_worker_lost=True)
def process_lecture_pipeline(self, lecture_id: str):
    """Celery task: execute the full processing pipeline for a lecture.

    Called after lecture upload. Runs all 8 stages sequentially.
    Retries on transient failures (max 3 times with exponential backoff).
    """
    logger.info("TASK: Starting pipeline for lecture %s (attempt %d/%d)", lecture_id, self.request.retries + 1, self.max_retries + 1)

    try:
        asyncio.run(_run_pipeline_async(lecture_id))
        logger.info("TASK: Pipeline complete for lecture %s", lecture_id)
    except Exception as exc:
        logger.exception("TASK: Pipeline failed for lecture %s", lecture_id)
        raise self.retry(exc=exc)


async def _run_pipeline_async(lecture_id: str):
    """Execute the pipeline within an async context with a DB session."""
    import uuid
    lid = uuid.UUID(lecture_id)
    settings = get_settings()

    async with async_session_maker() as session:
        try:
            await run_full_pipeline(session, lid, settings)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
