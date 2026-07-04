"""Authentication routes — register, login, refresh."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies.auth import get_current_user
from backend.src.core.dto.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
)
from backend.src.core.use_cases.auth.register import RegisterUseCase
from backend.src.core.use_cases.auth.login import LoginUseCase
from backend.src.core.use_cases.auth.refresh_token import RefreshTokenUseCase
from backend.src.infrastructure.db.models.user import UserModel
from backend.src.infrastructure.db.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    use_case = RegisterUseCase(session)
    return await use_case.execute(request)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_db),
):
    """Authenticate and receive JWT tokens."""
    use_case = LoginUseCase(session)
    return await use_case.execute(request)


@router.post("/refresh")
async def refresh(
    request: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db),
):
    """Refresh an expired access token using a refresh token."""
    use_case = RefreshTokenUseCase(session)
    return await use_case.execute(request.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserModel = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return UserResponse.model_validate(current_user)
