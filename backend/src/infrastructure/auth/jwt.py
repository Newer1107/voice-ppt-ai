"""JWT token creation and validation."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from jwt import PyJWTError

from backend.src.config.settings import Settings, get_settings


def create_access_token(
    data: dict[str, Any],
    settings: Optional[Settings] = None,
) -> str:
    """Create a short-lived JWT access token."""
    if settings is None:
        settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm="HS256")


def create_refresh_token(
    data: dict[str, Any],
    settings: Optional[Settings] = None,
) -> str:
    """Create a long-lived JWT refresh token with a unique JTI."""
    if settings is None:
        settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_EXPIRE_DAYS
    )
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(
    token: str,
    settings: Optional[Settings] = None,
) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Raises PyJWTError if the token is invalid or expired.
    """
    if settings is None:
        settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"],
        )
    except PyJWTError:
        raise
