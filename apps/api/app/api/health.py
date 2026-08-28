"""Liveness and readiness endpoints.

`/health` reports process liveness only and never touches external
dependencies, so it stays fast and always-available for orchestrators.
`/ready` additionally verifies the application database is reachable,
so it can be used as a real deploy/rollout gate.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.session import ping_database

router = APIRouter(tags=["health"])

DatabasePing = Callable[[], Awaitable[None]]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, str]


async def _default_database_ping() -> None:
    await ping_database()


def get_database_ping() -> DatabasePing:
    """FastAPI dependency provider; overridden in tests to avoid a real DB."""
    return _default_database_ping


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready")
async def ready(ping: DatabasePing = Depends(get_database_ping)) -> JSONResponse:
    try:
        await ping()
    except Exception as exc:  # noqa: BLE001 - readiness must report any failure, not crash
        body = ReadyResponse(status="not_ready", checks={"database": f"error: {exc}"})
        return JSONResponse(status_code=503, content=body.model_dump())

    body = ReadyResponse(status="ready", checks={"database": "ok"})
    return JSONResponse(status_code=200, content=body.model_dump())
