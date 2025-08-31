"""
Async database manager for PostgreSQL using SQLAlchemy 2.x and asyncpg.

- Reads the sync DATABASE_URL from Flask config or environment (e.g. "postgresql://user:pass@host:5432/db").
- Transparently adapts it to an async URL ("postgresql+asyncpg://...") for the async engine.
- Exposes `Base` for models and helpers to get an async session.

You can enable initialization from your Flask app by importing and calling `init_db(app)` in `app/__init__.py`.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

# Declarative base for models
Base = declarative_base()

# Module-level singletons (initialized via init_db)
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _to_async_url(database_url: str) -> str:
    """Convert a sync SQLAlchemy URL to an async one with asyncpg when needed.

    """
    if "+asyncpg" in database_url:
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # Any other scheme is unsupported in this setup (sqlite removed)
    return database_url


def init_db(app=None, *, database_url: Optional[str] = None) -> None:
    """Initialize the global async engine and session factory.

    Priority of config:
    1) explicit `database_url` arg
    2) Flask app config ["DATABASE_URL"] if `app` provided
    3) env var DATABASE_URL

    This function is safe to call multiple times; subsequent calls are no-ops
    if the engine is already initialized.
    """
    global _engine, _session_factory
    if _engine is not None and _session_factory is not None:
        return

    raw_url = (
        database_url
        or (app.config.get("DATABASE_URL") if app is not None else None)
        or os.getenv("DATABASE_URL")
    )

    if not raw_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set it in env or app config (expected postgresql or postgresql+asyncpg)."
        )

    async_url = _to_async_url(str(raw_url))

    # Create async engine and session factory
    # Use NullPool to avoid sharing asyncpg connections across different asyncio
    # event loops (e.g., Flask dev server threads/reloader), which can cause
    # "Future attached to a different loop" or "Event loop is closed" errors.
    _engine = create_async_engine(
        async_url,
        poolclass=NullPool,
        pool_pre_ping=True,
        future=True,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine is not initialized. Call init_db(app) first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Session factory is not initialized. Call init_db(app) first.")
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Async context manager that yields an `AsyncSession`.

    Usage:
        async with get_session() as session:
            await session.execute(...)
            await session.commit()
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        await session.close()


async def create_all() -> None:
    """Create database tables for all metadata registered under `Base`.

    Note: This issues SQL DDL; ensure the engine is initialized beforehand.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all() -> None:
    """Drop all tables (use with caution)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
