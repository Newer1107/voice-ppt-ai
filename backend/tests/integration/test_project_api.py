"""Project API integration tests.

S1: Create project returns 201
S2: List projects returns paginated results
S3: Get project returns project data
S4: Update project returns updated data
S5: Delete project returns 204
S6: Unauthorized access returns 401
"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def auth_token(client: AsyncClient) -> str:
    """Helper fixture: register + login, return access token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "proj@example.com", "password": "Test@1234", "full_name": "Project User"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "proj@example.com", "password": "Test@1234"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient, auth_token: str):
    """S1: Create a new project successfully."""
    response = await client.post(
        "/api/v1/projects",
        json={"title": "Test Project", "description": "A test project"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Project"
    assert data["description"] == "A test project"
    assert data["status"] == "active"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient, auth_token: str):
    """S2: List all projects for user."""
    # Create two projects
    for i in range(2):
        await client.post(
            "/api/v1/projects",
            json={"title": f"Project {i}", "description": f"Description {i}"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    response = await client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient, auth_token: str):
    """S3: Get a specific project by ID."""
    create_resp = await client.post(
        "/api/v1/projects",
        json={"title": "Get Test"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    project_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Get Test"


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient, auth_token: str):
    """S5: Delete project returns 204."""
    create_resp = await client.post(
        "/api/v1/projects",
        json={"title": "Delete Me"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    project_id = create_resp.json()["id"]

    response = await client.delete(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 204

    # Verify it's gone
    get_resp = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    """S6: Access without token returns 401."""
    response = await client.get("/api/v1/projects")
    assert response.status_code == 401
