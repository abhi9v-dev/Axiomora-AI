"""Alembic environment.

Runs migrations against the async engine used by the application (asyncpg),
so no second synchronous database driver is needed just for migrations.
Imports the ORM models and typed Settings directly from apps/api by path,
since /migrations is a sibling of /apps rather than nested inside apps/api
(see docs/06_DATA_MODEL_API_CONTRACTS.md repository layout).
"""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))

import app.db.action_models  # noqa: E402, F401  (registers runs.action on Base.metadata)
import app.db.catalog_models  # noqa: E402, F401  (registers catalog.* tables on Base.metadata)
import app.db.models  # noqa: E402, F401  (registers marketplace/organisation tables)
import app.db.run_models  # noqa: E402, F401  (registers runs.* tables on Base.metadata)
from app.config import Settings  # noqa: E402
from app.db.base import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# DATABASE_URL is never stored in alembic.ini; read it the same way the app
# does. Prefer apps/api/.env (typical local dev) but fall back to real
# environment variables (typical CI) when no .env file is present.
_api_env_file = API_DIR / ".env"
_settings = Settings(_env_file=str(_api_env_file) if _api_env_file.exists() else None)  # type: ignore[call-arg]
config.set_main_option("sqlalchemy.url", _settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Emit migration SQL without a live database connection (`--sql`)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, include_schemas=True)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
