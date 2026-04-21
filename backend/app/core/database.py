"""
CodeSentinel — Async Database Engine
SQLAlchemy 2.0 async with session factory and health check.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _normalize_db_url(url: str) -> str:
    """Ensure the DATABASE_URL uses the asyncpg driver for async SQLAlchemy.

    Render/Railway provide URLs like ``postgresql://...`` which default to
    the synchronous psycopg2 driver.  ``create_async_engine`` requires
    ``postgresql+asyncpg://...``.  This helper transparently rewrites the
    scheme so the worker never crashes with:
        'The asyncio extension requires an async driver to be used.'
    """
    if url.startswith("postgresql+asyncpg://"):
        return url                                        # already correct
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):                     # legacy Heroku-style
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def _create_engine() -> AsyncEngine:
    db_url = _normalize_db_url(settings.DATABASE_URL)
    kwargs: dict = {"echo": settings.DATABASE_ECHO, "pool_pre_ping": True}
    if settings.APP_ENV == "testing":
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
        kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW
        kwargs["pool_timeout"] = settings.DATABASE_POOL_TIMEOUT
    return create_async_engine(db_url, **kwargs)


engine: AsyncEngine = _create_engine()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a session that auto-commits on success."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for Celery tasks and scripts."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_redis_connection() -> bool:
    try:
        import redis.asyncio as redis
        from app.core.config import settings
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        return await r.ping()
    except Exception:
        return False


async def ensure_schema() -> None:
    """Create any missing tables from ORM metadata.

    This is a safety net for environments where an older migration revision
    may have been marked as applied before full schema additions existed.
    """
    # Ensure model modules are imported so all table metadata is registered.
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
