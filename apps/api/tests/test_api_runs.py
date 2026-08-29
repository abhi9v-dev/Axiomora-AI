"""FastAPI route tests for app.api.runs: request/response shapes, status
codes and background-task scheduling -- all without a real database, LLM
or warehouse call.

app.orchestrator.store/service functions are monkeypatched at the
app.api.runs import site (the names that module's endpoint functions
actually call), backed by an in-memory fake. The state machine itself is
covered by test_orchestrator_service.py, and real persistence by
test_run_store_integration.py; this file only exercises the HTTP layer:
routing, status codes, error mapping, and that the right function gets
scheduled with the right arguments.
"""

from __future__ import annotations

import datetime as dt
import time
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.runs as runs_module
from app.api.deps import get_session
from app.main import create_app
from app.orchestrator.events import get_event_bus
from app.orchestrator.schema import RunSnapshot, RunSummary
from app.orchestrator.service import NotAwaitingClarificationError


def _snapshot(run_id: uuid.UUID, *, status: str = "RECEIVED", **overrides: object) -> RunSnapshot:
    now = dt.datetime.now(dt.UTC)
    data: dict[str, object] = dict(
        run_id=run_id,
        tenant_id="default",
        source_id="marketplace_demo",
        question="Why did hold time spike?",
        status=status,
        created_at=now,
        updated_at=now,
    )
    data.update(overrides)
    return RunSnapshot.model_validate(data)


class _FakeBackend:
    def __init__(self) -> None:
        self.runs: dict[uuid.UUID, RunSnapshot] = {}
        self.executed: list[tuple[uuid.UUID, str]] = []

    async def create_run(
        self, *, session: object, tenant_id: str, source_id: str, question: str
    ) -> RunSnapshot:
        snapshot = _snapshot(
            uuid.uuid4(), tenant_id=tenant_id, source_id=source_id, question=question
        )
        self.runs[snapshot.run_id] = snapshot
        return snapshot

    async def get_run(self, session: object, run_id: uuid.UUID) -> RunSnapshot | None:
        return self.runs.get(run_id)

    async def list_runs(self, session: object, *, tenant_id: str, limit: int) -> list[RunSummary]:
        items = sorted(self.runs.values(), key=lambda r: r.created_at, reverse=True)[:limit]
        return [
            RunSummary(
                run_id=r.run_id, question=r.question, status=r.status, created_at=r.created_at
            )
            for r in items
        ]

    async def record_clarification(
        self, *, session: object, run_id: uuid.UUID, answer: str
    ) -> tuple[RunSnapshot, str]:
        snapshot = self.runs.get(run_id)
        if snapshot is None:
            raise LookupError("no such run")
        if snapshot.status != "NEEDS_CLARIFICATION":
            raise NotAwaitingClarificationError("not awaiting clarification")
        snapshot.status = "RECEIVED"
        snapshot.clarification_answer = answer
        return snapshot, f"{snapshot.question}\n\nClarification: {answer}"

    async def cancel_run(self, session: object, run_id: uuid.UUID) -> RunSnapshot | None:
        snapshot = self.runs.get(run_id)
        if snapshot is None:
            return None
        snapshot.status = "CANCELLED"
        return snapshot

    async def execute_run(self, **kwargs: object) -> None:
        snapshot = kwargs["snapshot"]
        assert isinstance(snapshot, RunSnapshot)
        effective_question = kwargs["effective_question"]
        assert isinstance(effective_question, str)
        self.executed.append((snapshot.run_id, effective_question))
        snapshot.status = "READY"


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> _FakeBackend:
    fake = _FakeBackend()
    monkeypatch.setattr(runs_module, "create_run", fake.create_run)
    monkeypatch.setattr(runs_module, "get_run", fake.get_run)
    monkeypatch.setattr(runs_module, "list_runs", fake.list_runs)
    monkeypatch.setattr(runs_module, "record_clarification", fake.record_clarification)
    monkeypatch.setattr(runs_module, "cancel_run", fake.cancel_run)
    monkeypatch.setattr(runs_module, "execute_run", fake.execute_run)
    runs_module._TASKS.clear()
    return fake


async def _fake_session() -> object:
    yield None


@pytest.fixture
def client(backend: _FakeBackend) -> Iterator[TestClient]:
    application: FastAPI = create_app()
    application.dependency_overrides[get_session] = _fake_session
    with TestClient(application) as test_client:
        yield test_client


def _wait_until(predicate: object, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return True
        time.sleep(0.01)
    return False


def test_start_run_returns_202_with_run_id_and_schedules_execution(
    client: TestClient, backend: _FakeBackend
) -> None:
    response = client.post(
        "/api/v1/runs",
        json={"question": "Why did hold time spike?", "source_id": "marketplace_demo"},
    )

    assert response.status_code == 202
    body = response.json()
    run_id = uuid.UUID(body["run_id"])
    assert body["status"] == "RECEIVED"

    assert _wait_until(lambda: backend.executed)
    executed_run_id, executed_question = backend.executed[0]
    assert executed_run_id == run_id
    assert executed_question == "Why did hold time spike?"


def test_start_run_rejects_blank_question(client: TestClient) -> None:
    response = client.post("/api/v1/runs", json={"question": "   "})

    assert response.status_code == 422


def test_start_run_defaults_source_id_when_omitted(
    client: TestClient, backend: _FakeBackend
) -> None:
    response = client.post("/api/v1/runs", json={"question": "How many stuck projects?"})

    assert response.status_code == 202
    run_id = uuid.UUID(response.json()["run_id"])
    assert backend.runs[run_id].source_id == "marketplace_demo"


def test_get_run_returns_the_stored_snapshot(client: TestClient, backend: _FakeBackend) -> None:
    snapshot = _snapshot(uuid.uuid4(), status="READY")
    backend.runs[snapshot.run_id] = snapshot

    response = client.get(f"/api/v1/runs/{snapshot.run_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "READY"


def test_get_run_returns_404_for_unknown_run(client: TestClient) -> None:
    response = client.get(f"/api/v1/runs/{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_runs_returns_history_newest_first(client: TestClient, backend: _FakeBackend) -> None:
    older = _snapshot(uuid.uuid4(), created_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    newer = _snapshot(uuid.uuid4(), created_at=dt.datetime(2026, 6, 1, tzinfo=dt.UTC))
    backend.runs[older.run_id] = older
    backend.runs[newer.run_id] = newer

    response = client.get("/api/v1/runs")

    assert response.status_code == 200
    ids = [item["run_id"] for item in response.json()]
    assert ids == [str(newer.run_id), str(older.run_id)]


def test_submit_clarification_resumes_a_paused_run(
    client: TestClient, backend: _FakeBackend
) -> None:
    snapshot = _snapshot(uuid.uuid4(), status="NEEDS_CLARIFICATION")
    backend.runs[snapshot.run_id] = snapshot

    response = client.post(
        f"/api/v1/runs/{snapshot.run_id}/clarification", json={"answer": "the Buyer department"}
    )

    assert response.status_code == 202
    assert _wait_until(lambda: backend.executed)
    _, effective_question = backend.executed[0]
    assert "the Buyer department" in effective_question


def test_submit_clarification_rejects_blank_answer(
    client: TestClient, backend: _FakeBackend
) -> None:
    snapshot = _snapshot(uuid.uuid4(), status="NEEDS_CLARIFICATION")
    backend.runs[snapshot.run_id] = snapshot

    response = client.post(f"/api/v1/runs/{snapshot.run_id}/clarification", json={"answer": " "})

    assert response.status_code == 422


def test_submit_clarification_404s_for_unknown_run(client: TestClient) -> None:
    response = client.post(f"/api/v1/runs/{uuid.uuid4()}/clarification", json={"answer": "x"})

    assert response.status_code == 404


def test_submit_clarification_409s_when_run_not_awaiting_it(
    client: TestClient, backend: _FakeBackend
) -> None:
    snapshot = _snapshot(uuid.uuid4(), status="READY")
    backend.runs[snapshot.run_id] = snapshot

    response = client.post(f"/api/v1/runs/{snapshot.run_id}/clarification", json={"answer": "x"})

    assert response.status_code == 409


def test_cancel_run_returns_the_cancelled_snapshot(
    client: TestClient, backend: _FakeBackend
) -> None:
    snapshot = _snapshot(uuid.uuid4(), status="GENERATING_SQL")
    backend.runs[snapshot.run_id] = snapshot

    response = client.post(f"/api/v1/runs/{snapshot.run_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


def test_cancel_run_404s_for_unknown_run(client: TestClient) -> None:
    response = client.post(f"/api/v1/runs/{uuid.uuid4()}/cancel")

    assert response.status_code == 404


def test_events_stream_404s_for_unknown_run(client: TestClient) -> None:
    response = client.get(f"/api/v1/runs/{uuid.uuid4()}/events")

    assert response.status_code == 404


def test_events_stream_replays_a_terminal_snapshot_and_closes(
    client: TestClient, backend: _FakeBackend
) -> None:
    snapshot = _snapshot(uuid.uuid4(), status="READY")
    backend.runs[snapshot.run_id] = snapshot
    # Seed the bus buffer directly (bypassing the async publish lock, which
    # would need its own event loop from this synchronous test) with an
    # already-terminal snapshot, so bus.subscribe() replays it and returns
    # immediately -- letting TestClient's buffering GET complete rather than
    # hang waiting on a queue.get() that would otherwise never resolve.
    get_event_bus(snapshot.run_id)._buffer.append(snapshot)  # noqa: SLF001

    response = client.get(f"/api/v1/runs/{snapshot.run_id}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: run_update" in response.text
    assert str(snapshot.run_id) in response.text
