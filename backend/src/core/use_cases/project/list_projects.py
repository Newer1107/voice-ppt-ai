"""List projects use case with pagination."""

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.dto.project import ProjectResponse, PaginatedResponse
from backend.src.infrastructure.db.repositories.project_repo import ProjectRepository


class ListProjectsUseCase:
    """Handle paginated project listing."""

    def __init__(self, session: AsyncSession):
        self._repo = ProjectRepository(session)

    async def execute(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> dict:
        skip = (page - 1) * page_size
        projects, total = await self._repo.list_by_user(
            user_id=user_id,
            skip=skip,
            limit=page_size,
            status=status,
        )

        items = []
        for p in projects:
            resp = ProjectResponse.model_validate(p)
            resp.lecture_count = len(p.lectures) if hasattr(p, "lectures") else 0
            items.append(resp)

        total_pages = max(1, (total + page_size - 1) // page_size)

        return {
            "items": [item.model_dump() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
