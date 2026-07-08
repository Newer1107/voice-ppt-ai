"""Get lecture status use case — tracks processing progress."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import NotFoundError
from backend.src.core.dto.lecture import (
    LectureStatusResponse,
    JobSummaryResponse,
)
from backend.src.infrastructure.db.repositories.lecture_repo import LectureRepository
from backend.src.infrastructure.db.repositories.job_repo import JobRepository
from backend.src.infrastructure.db.repositories.project_repo import ProjectRepository

# Stage ordering for progress tracking
PIPELINE_STAGES = [
    "extract_audio",
    "transcribe",
    "parse_pptx",
    "generate_embeddings",
    "align_transcript",
    "generate_narration",
    "generate_tts",
    "embed_narration",
]

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


class GetLectureStatusUseCase:
    """Handle lecture processing status retrieval."""

    def __init__(self, session: AsyncSession):
        self._lecture_repo = LectureRepository(session)
        self._job_repo = JobRepository(session)

    async def execute(
        self, user_id: uuid.UUID, lecture_id: uuid.UUID
    ) -> LectureStatusResponse:
        lecture = await self._lecture_repo.get(lecture_id)
        if not lecture:
            raise NotFoundError(message="Lecture not found")

        # Verify project ownership
        project_repo = ProjectRepository(self._lecture_repo._session)
        project = await project_repo.find_by_user_and_id(
            user_id, lecture.project_id
        )
        if not project:
            raise NotFoundError(message="Lecture not found")

        # Get associated jobs
        jobs = await self._job_repo.list_by_lecture(lecture_id)
        job_summaries = [
            JobSummaryResponse(
                id=job.id,
                job_type=job.job_type,
                status=job.status,
                progress=job.progress,
            )
            for job in jobs
        ]

        # Compute overall progress
        overall_progress = self._compute_progress(jobs)

        # Determine current stage
        current_stage = self._get_current_stage(jobs)

        return LectureStatusResponse(
            id=lecture.id,
            status=lecture.status,
            progress=overall_progress,
            current_stage=current_stage,
            jobs=job_summaries,
            error_message=lecture.error_message,
        )

    def _compute_progress(self, jobs: list) -> float:
        if not jobs:
            return 0.0

        total = 0.0
        for job in jobs:
            weight = STAGE_WEIGHTS.get(job.job_type, 0.0)
            if job.status == "completed":
                total += weight
            elif job.status == "running":
                total += weight * job.progress
            elif job.status == "failed":
                # Failed jobs contribute their full weight (pipeline stops)
                pass

        return min(total, 1.0)

    def _get_current_stage(self, jobs: list) -> str | None:
        for stage in PIPELINE_STAGES:
            matching = [j for j in jobs if j.job_type == stage]
            if not matching:
                return stage
            job = matching[0]
            if job.status == "pending":
                return stage
            if job.status == "running":
                return f"Processing: {stage.replace('_', ' ').title()}"
        return None
