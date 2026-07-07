"""Project CRUD routes."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies.auth import get_current_user
from backend.src.core.dto.project import (
    CreateProjectRequest,
    UpdateProjectRequest,
    ProjectDetailResponse,
    ProjectResponse,
)
from backend.src.core.use_cases.project.create_project import CreateProjectUseCase
from backend.src.core.use_cases.project.list_projects import ListProjectsUseCase
from backend.src.core.use_cases.project.get_project import GetProjectUseCase
from backend.src.core.use_cases.project.update_project import UpdateProjectUseCase
from backend.src.core.use_cases.project.delete_project import DeleteProjectUseCase
from backend.src.infrastructure.db.models.user import UserModel
from backend.src.infrastructure.db.session import get_db

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Projects"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all projects for the current user with pagination."""
    use_case = ListProjectsUseCase(session)
    return await use_case.execute(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
    )


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: CreateProjectRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    use_case = CreateProjectUseCase(session)
    return await use_case.execute(user_id=current_user.id, request=request)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get a single project by ID."""
    use_case = GetProjectUseCase(session)
    return await use_case.execute(user_id=current_user.id, project_id=project_id)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    request: UpdateProjectRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Update a project."""
    use_case = UpdateProjectUseCase(session)
    return await use_case.execute(
        user_id=current_user.id,
        project_id=project_id,
        request=request,
    )


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Delete a project and all associated data."""
    use_case = DeleteProjectUseCase(session)
    return await use_case.execute(user_id=current_user.id, project_id=project_id)
