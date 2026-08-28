from __future__ import annotations

import os

# Set required settings before app.config.Settings is ever instantiated, so the
# suite never depends on a real .env file or a live database. Must run before
# the app/fastapi imports below, hence the noqa: E402 on each of those.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://bi_app:changeme@localhost:5432/bi_copilot_test"
)
os.environ.setdefault(
    "WAREHOUSE_URL", "postgresql+asyncpg://bi_readonly:changeme@localhost:5432/bi_copilot_test"
)

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
