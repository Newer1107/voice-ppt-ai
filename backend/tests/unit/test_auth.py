"""Unit tests for auth infrastructure.

T1: JWT token creation and validation
T2: Password hashing and verification
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jwt import PyJWTError

from backend.src.infrastructure.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from backend.src.infrastructure.auth.password import hash_password, verify_password


class TestJWT:
    """Test JWT token creation, decoding, and validation."""

    def test_create_and_decode_access_token(self):
        """S1: Create an access token and decode it successfully."""
        user_id = str(uuid.uuid4())
        token = create_access_token({"sub": user_id})
        assert isinstance(token, str)
        assert len(token) > 50

        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_and_decode_refresh_token(self):
        """S2: Create a refresh token with JTI."""
        user_id = str(uuid.uuid4())
        token = create_refresh_token({"sub": user_id})
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"
        assert "jti" in payload

    def test_expired_token_raises_error(self):
        """S3: Expired token should raise PyJWTError."""
        # Create token that's already expired
        from backend.src.config.settings import get_settings
        settings = get_settings()
        import jwt as pyjwt
        expired = pyjwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "type": "access",
            },
            settings.JWT_SECRET_KEY,
            algorithm="HS256",
        )
        with pytest.raises(PyJWTError):
            decode_token(expired)

    def test_invalid_token_signature(self):
        """S4: Token with wrong signature should raise PyJWTError."""
        # Create token with different secret
        import jwt as pyjwt
        fake = pyjwt.encode(
            {"sub": str(uuid.uuid4()), "type": "access"},
            "wrong-secret-key",
            algorithm="HS256",
        )
        with pytest.raises(PyJWTError):
            decode_token(fake)


class TestPassword:
    """Test password hashing and verification."""

    def test_hash_and_verify(self):
        """S1: Hash a password and verify it matches."""
        password = "Test@1234"
        hashed = hash_password(password)
        assert hashed != password
        assert hashed.startswith("$2b$")
        assert verify_password(password, hashed)

    def test_wrong_password(self):
        """S2: Wrong password should not verify."""
        hashed = hash_password("CorrectP@ss1")
        assert not verify_password("WrongP@ss1", hashed)

    def test_different_hashes_for_same_password(self):
        """S3: Same password produces different hashes (salting)."""
        password = "Test@1234"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2
