"""Async SQLAlchemy engine access for the application database."""

from __future__ import annotations

import contextlib
from functools import lru_cache
from typing import Any

from pgvector.asyncpg import register_vector
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings


async def _try_register_vector(conn: Any) -> None:
    # The `vector` Postgres type doesn't exist until migration 0002's
    # `CREATE EXTENSION vector` has run -- e.g. every connection made while
    # applying migrations to a brand-new database. register_vector raises
    # unconditionally in that case (unlike its own halfvec/sparsevec
    # sub-registrations, which it already tolerates missing). Swallow it
    # here so non-vector queries -- like the /ready health check -- keep
    # working regardless of migration state; a connection made after the
    # extension exists will register successfully.
    with contextlib.suppress(Exception):
        await register_vector(conn)


def register_pgvector_codec(engine: AsyncEngine) -> None:
    """Register asyncpg's `vector` type codec on every new connection.

    Required for the `pgvector.sqlalchemy.Vector` column type (see
    app.db.catalog_models) to (de)serialize correctly over asyncpg -- SQLAlchemy
    has no built-in knowledge of the pgvector wire format. Harmless to call for
    engines that never touch a vector column. Pattern per SQLAlchemy's own
    AsyncAdapt_asyncpg_connection.run_async docs for async-only connection setup.
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _connect(dbapi_connection: Any, _connection_record: Any) -> None:
        dbapi_connection.run_async(_try_register_vector)


@lru_cache
def get_engine() -> AsyncEngine:
    """Return the process-wide async engine for DATABASE_URL, created lazily."""
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    register_pgvector_codec(engine)
    return engine


@lru_cache
def get_warehouse_engine() -> AsyncEngine:
    """Return the process-wide async engine for WAREHOUSE_URL (the
    bi_readonly role), created lazily. Only ever used to execute SQL that
    has already passed app.validator.policy (see app.validator.executor) --
    never for arbitrary queries."""
    settings = get_settings()
    return create_async_engine(settings.WAREHOUSE_URL, pool_pre_ping=True)


async def ping_database(engine: AsyncEngine | None = None) -> None:
    """Raise if the application database cannot be reached."""
    active_engine = engine if engine is not None else get_engine()
    async with active_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
