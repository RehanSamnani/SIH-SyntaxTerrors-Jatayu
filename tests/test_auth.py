import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from typing import AsyncGenerator

from app.main import app
from app.db import Base, engine, get_db
from app.models.user import User, UserRole

# Test data
TEST_USER = {
    "email": "test@example.com",
    "password": "testpassword123",
    "name": "Test User",
    "role": UserRole.OPERATOR
}

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
async def setup_db():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def async_client() -> AsyncGenerator:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_register_user(async_client: AsyncClient):
    response = await async_client.post("/auth/register", json=TEST_USER)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_USER["email"]
    assert data["name"] == TEST_USER["name"]
    assert data["role"] == TEST_USER["role"]
    assert "id" in data
    assert "password_hash" not in data

@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    # First registration
    await async_client.post("/auth/register", json=TEST_USER)
    # Attempt duplicate registration
    response = await async_client.post("/auth/register", json=TEST_USER)
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    # Register user first
    await async_client.post("/auth/register", json=TEST_USER)
    
    # Login
    response = await async_client.post(
        "/auth/login",
        data={
            "username": TEST_USER["email"],
            "password": TEST_USER["password"]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient):
    # Register user first
    await async_client.post("/auth/register", json=TEST_USER)
    
    # Login with wrong password
    response = await async_client.post(
        "/auth/login",
        data={
            "username": TEST_USER["email"],
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_me(async_client: AsyncClient):
    # Register user
    await async_client.post("/auth/register", json=TEST_USER)
    
    # Login to get token
    login_response = await async_client.post(
        "/auth/login",
        data={
            "username": TEST_USER["email"],
            "password": TEST_USER["password"]
        }
    )
    token = login_response.json()["access_token"]
    
    # Get user profile
    response = await async_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_USER["email"]
    assert data["name"] == TEST_USER["name"]
    assert data["role"] == TEST_USER["role"]