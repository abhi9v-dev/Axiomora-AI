"""Async SQLAlchemy engine access for the application database.

Phase 0 only needs a connectivity check for the readiness endpoint. ORM
models, sessions-per-request and migrations are introduced in Phase 1
alongside the retail star schema.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Return the process-wide async engine for DATABASE_URL, created lazily."""
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)


async def ping_database(engine: AsyncEngine | None = None) -> None:
    """Raise if the application database cannot be reached."""
    active_engine = engine if engine is not None else get_engine()
    async with active_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
