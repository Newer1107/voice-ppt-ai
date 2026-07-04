"""FastAPI dependency injection for authentication."""

from typing import Optional

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import UnauthorizedError
from backend.src.infrastructure.auth.jwt import decode_token
from backend.src.infrastructure.db.models.user import UserModel
from backend.src.infrastructure.db.repositories.user_repo import UserRepository
from backend.src.infrastructure.db.session import get_db

# Token extraction schemes
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=True,
)


async def get_current_user(
    session: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> UserModel:
    """Validate JWT token and return the current user.

    Raises UnauthorizedError if token is invalid or user not found.
    """
    try:
        payload = decode_token(token)
    except PyJWTError:
        raise UnauthorizedError(message="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(message="Invalid token payload")

    repo = UserRepository(session)
    user = await repo.get(user_id)
    if not user or not user.is_active:
        raise UnauthorizedError(message="User not found or inactive")

    return user


async def get_optional_user(
    session: AsyncSession = Depends(get_db),
    request: Request = None,
) -> Optional[UserModel]:
    """Optionally resolve the current user from the token.

    Returns None if no valid token is provided (for public-but-personalized endpoints).
    """
    auth_header = request.headers.get("Authorization") if request else None
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    try:
        payload = decode_token(token)
    except PyJWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    repo = UserRepository(session)
    user = await repo.get(user_id)
    return user if user and user.is_active else None
