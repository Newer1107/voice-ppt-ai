"""Login use case — authenticates a user and returns JWT tokens."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import UnauthorizedError
from backend.src.core.dto.auth import LoginRequest, TokenResponse
from backend.src.infrastructure.auth.jwt import create_access_token, create_refresh_token
from backend.src.infrastructure.auth.password import verify_password
from backend.src.infrastructure.db.repositories.user_repo import UserRepository
from backend.src.config.settings import get_settings


class LoginUseCase:
    """Handle user authentication."""

    def __init__(self, session: AsyncSession):
        self._repo = UserRepository(session)

    async def execute(self, request: LoginRequest) -> TokenResponse:
        settings = get_settings()

        # Find user
        user = await self._repo.find_by_email(request.email)
        if not user:
            raise UnauthorizedError(
                message="Invalid email or password",
            )

        # Check if active
        if not user.is_active:
            raise UnauthorizedError(
                message="Account is disabled",
            )

        # Verify password
        if not verify_password(request.password, user.password_hash):
            raise UnauthorizedError(
                message="Invalid email or password",
            )

        # Create tokens
        token_data = {"sub": str(user.id)}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
        )
