"""Refresh token use case — issues a new access token."""

from jwt import PyJWTError

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import UnauthorizedError
from backend.src.infrastructure.auth.jwt import create_access_token, decode_token
from backend.src.config.settings import get_settings


class RefreshTokenUseCase:
    """Handle token refresh."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def execute(self, refresh_token: str) -> dict:
        settings = get_settings()

        # Decode and validate refresh token
        try:
            payload = decode_token(refresh_token)
        except PyJWTError:
            raise UnauthorizedError(message="Invalid or expired refresh token")

        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            raise UnauthorizedError(message="Invalid token type")

        # Issue new access token
        token_data = {"sub": payload.get("sub")}
        access_token = create_access_token(token_data)

        return {
            "access_token": access_token,
            "expires_in": settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
        }
