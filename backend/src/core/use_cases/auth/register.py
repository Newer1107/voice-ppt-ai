"""Register use case — creates a new user account."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.errors.handlers import ConflictError
from backend.src.core.dto.auth import RegisterRequest, UserResponse
from backend.src.infrastructure.auth.password import hash_password
from backend.src.infrastructure.db.models.user import UserModel
from backend.src.infrastructure.db.repositories.user_repo import UserRepository


class RegisterUseCase:
    """Handle user registration."""

    def __init__(self, session: AsyncSession):
        self._repo = UserRepository(session)

    async def execute(self, request: RegisterRequest) -> UserResponse:
        # Check for existing email
        existing = await self._repo.find_by_email(request.email)
        if existing:
            raise ConflictError(
                message="A user with this email already exists",
                details={"email": request.email},
            )

        # Create user
        user = UserModel(
            email=request.email,
            password_hash=hash_password(request.password),
            full_name=request.full_name,
        )
        user = await self._repo.add(user)

        return UserResponse.model_validate(user)
