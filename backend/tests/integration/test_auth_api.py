"""Auth API integration tests.

S1: User registration creates account and returns user data
S2: Duplicate email returns 409
S3: Login with valid credentials returns tokens
S4: Login with wrong password returns 401
S5: Token refresh works
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """S1: Register a new user successfully."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "Test@1234",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """S2: Registering with an existing email returns 409."""
    # First registration
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "Test@1234", "full_name": "User 1"},
    )
    # Second registration with same email
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "Test@5678", "full_name": "User 2"},
    )
    assert response.status_code == 409
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """S3: Login with valid credentials returns JWT tokens."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "Test@1234", "full_name": "Login User"},
    )
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "Test@1234"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """S4: Login with wrong password returns 401."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@example.com", "password": "Test@1234", "full_name": "User"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "WrongP@ss1"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_invalid_password(client: AsyncClient):
    """S5: Register with weak password returns 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "short", "full_name": "User"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient):
    """S6: GET /auth/me returns current user."""
    # Register
    await client.post(
        "/api/v1/auth/register",
        json={"email": "me@example.com", "password": "Test@1234", "full_name": "Me User"},
    )
    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": "Test@1234"},
    )
    token = login_resp.json()["access_token"]

    # Get me
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"
