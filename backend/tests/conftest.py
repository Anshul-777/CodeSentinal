"""
CodeSentinel — Test Configuration
Full async test setup with real PostgreSQL test database.
"""
from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Override DATABASE_URL to point to test DB before importing app
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://codesentinel:password@localhost:5432/codesentinel_test"
)
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("ENCRYPTION_KEY", "")  # Will be auto-generated in testing mode

from app.core.database import Base
from app.main import app

pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: requires PostgreSQL test database"
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine and tables."""
    test_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(test_url, poolclass=NullPool, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional test database session."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Register a test user and return auth headers."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "pytest@codesentinel.test",
        "password": "TestPass#1234",
        "full_name": "Pytest User",
        "job_title": "Security Engineer",
        "company": "Test Corp",
        "organization_name": "Pytest Org",
        "use_case": "Automated testing for CodeSentinel CI/CD pipeline integration",
        "agree_to_terms": True,
    })
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
