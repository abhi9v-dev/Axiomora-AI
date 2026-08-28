from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.health import get_database_ping


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_200_when_database_reachable(app: FastAPI, client: TestClient) -> None:
    async def fake_ping_ok() -> None:
        return None

    app.dependency_overrides[get_database_ping] = lambda: fake_ping_ok

    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


def test_ready_returns_503_when_database_unreachable(app: FastAPI, client: TestClient) -> None:
    async def fake_ping_fail() -> None:
        raise ConnectionError("could not connect to server")

    app.dependency_overrides[get_database_ping] = lambda: fake_ping_fail

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert "could not connect" in body["checks"]["database"]
