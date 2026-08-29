"""FastAPI route tests for app.api.actions: status codes, idempotent
replay, policy rejection and error mapping -- all without a real database.

app.orchestrator.store.get_run and app.action.store's functions are
monkeypatched at the app.api.actions import site, backed by an in-memory
fake (same pattern as test_api_runs.py). app.action.workbook.build_workbook
runs for real -- it's pure, fast, and already unit-tested on its own in
test_workbook.py -- so these tests also verify a real .xlsx comes back.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.exc import IntegrityError

import app.api.actions as actions_module
from app.action.schema import ActionRecord
from app.api.deps import get_session
from app.insight.schema import InsightOutput
from app.main import create_app
from app.nl2sql.schema import NL2SQLOutput
from app.orchestrator.schema import AttemptRecord, RunSnapshot
from app.validator.schema import QueryResult, ValidationCheck, ValidatorOutput


def _snapshot(run_id: uuid.UUID, *, status: str = "READY", ready: bool = True) -> RunSnapshot:
    now = dt.datetime.now(dt.UTC)
    attempts = []
    if ready:
        attempts = [
            AttemptRecord(
                attempt_no=1,
                nl2sql=NL2SQLOutput(sql="SELECT 1", dialect="postgres", confidence=0.9),
                validator=ValidatorOutput(
                    status="pass",
                    checks=[ValidationCheck(name="sql_policy", status="pass", details="ok")],
                    repairable=False,
                    result=QueryResult(columns=["x"], rows=[[1]], row_count=1, truncated=False),
                ),
            )
        ]
    return RunSnapshot(
        run_id=run_id,
        tenant_id="default",
        source_id="marketplace_demo",
        question="Why did hold time spike?",
        status=status,
        attempts=attempts,
        insight=InsightOutput(headline="h", narrative="n") if ready else None,
        created_at=now,
        updated_at=now,
        completed_at=now if ready else None,
    )


class _FakeBackend:
    def __init__(self) -> None:
        self.runs: dict[uuid.UUID, RunSnapshot] = {}
        self.actions: dict[tuple[uuid.UUID, str], ActionRecord] = {}
        self.record_calls = 0

    async def get_run(self, session: object, run_id: uuid.UUID) -> RunSnapshot | None:
        return self.runs.get(run_id)

    async def get_action_by_idempotency_key(
        self, session: object, run_id: uuid.UUID, idempotency_key: str
    ) -> ActionRecord | None:
        return self.actions.get((run_id, idempotency_key))

    async def record_action(self, session: object, record: ActionRecord) -> ActionRecord:
        self.record_calls += 1
        key = (record.run_id, record.idempotency_key)
        if key in self.actions:
            raise IntegrityError("duplicate", {}, Exception("uq_action_run_idempotency_key"))
        self.actions[key] = record
        return record


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> _FakeBackend:
    fake = _FakeBackend()
    monkeypatch.setattr(actions_module, "get_run", fake.get_run)
    monkeypatch.setattr(
        actions_module, "get_action_by_idempotency_key", fake.get_action_by_idempotency_key
    )
    monkeypatch.setattr(actions_module, "record_action", fake.record_action)
    return fake


class _FakeSession:
    """Stands in for AsyncSession -- the fake store functions never touch
    it for real queries, but app.api.actions calls session.rollback()
    after a simulated IntegrityError, so it needs to support that much."""

    async def rollback(self) -> None:
        return None


async def _fake_session() -> object:
    yield _FakeSession()


@pytest.fixture
def client(backend: _FakeBackend) -> Iterator[TestClient]:
    application: FastAPI = create_app()
    application.dependency_overrides[get_session] = _fake_session
    with TestClient(application) as test_client:
        yield test_client


def test_export_excel_returns_a_real_workbook_for_a_ready_run(
    client: TestClient, backend: _FakeBackend
) -> None:
    run_id = uuid.uuid4()
    backend.runs[run_id] = _snapshot(run_id)

    response = client.post(
        f"/api/v1/runs/{run_id}/actions",
        json={"type": "export_excel", "idempotency_key": "key-1"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "attachment" in response.headers["content-disposition"]
    assert "X-Action-Id" in response.headers

    workbook = load_workbook(BytesIO(response.content))
    assert workbook.sheetnames == ["Summary", "Data", "SQL & Evidence", "Validation"]
    assert backend.record_calls == 1


def test_repeating_the_same_idempotency_key_does_not_record_a_second_action(
    client: TestClient, backend: _FakeBackend
) -> None:
    run_id = uuid.uuid4()
    backend.runs[run_id] = _snapshot(run_id)
    body = {"type": "export_excel", "idempotency_key": "same-key"}

    first = client.post(f"/api/v1/runs/{run_id}/actions", json=body)
    second = client.post(f"/api/v1/runs/{run_id}/actions", json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert backend.record_calls == 1
    assert first.headers["X-Action-Id"] == second.headers["X-Action-Id"]


def test_a_power_bi_action_is_rejected_and_recorded(
    client: TestClient, backend: _FakeBackend
) -> None:
    run_id = uuid.uuid4()
    backend.runs[run_id] = _snapshot(run_id)

    response = client.post(
        f"/api/v1/runs/{run_id}/actions",
        json={"type": "power_bi_push", "idempotency_key": "key-1"},
    )

    assert response.status_code == 403
    assert "not available yet" in response.json()["detail"]
    recorded = backend.actions[(run_id, "key-1")]
    assert recorded.status == "rejected"


def test_a_repeated_rejected_request_stays_rejected_without_recording_again(
    client: TestClient, backend: _FakeBackend
) -> None:
    run_id = uuid.uuid4()
    backend.runs[run_id] = _snapshot(run_id)
    body = {"type": "power_bi_push", "idempotency_key": "key-1"}

    client.post(f"/api/v1/runs/{run_id}/actions", json=body)
    second = client.post(f"/api/v1/runs/{run_id}/actions", json=body)

    assert second.status_code == 403
    assert backend.record_calls == 1


def test_export_is_rejected_when_the_run_is_not_ready(
    client: TestClient, backend: _FakeBackend
) -> None:
    run_id = uuid.uuid4()
    backend.runs[run_id] = _snapshot(run_id, status="GENERATING_SQL", ready=False)

    response = client.post(
        f"/api/v1/runs/{run_id}/actions",
        json={"type": "export_excel", "idempotency_key": "key-1"},
    )

    assert response.status_code == 403


def test_unknown_run_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/runs/{uuid.uuid4()}/actions",
        json={"type": "export_excel", "idempotency_key": "key-1"},
    )

    assert response.status_code == 404


async def test_a_concurrent_duplicate_insert_recovers_via_the_winning_row(
    client: TestClient, backend: _FakeBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = uuid.uuid4()
    backend.runs[run_id] = _snapshot(run_id)

    # Simulate two requests racing on the same idempotency key: this
    # request's own pre-check sees nothing (as if it ran before the other
    # request's commit), but by the time record_action actually runs, the
    # other request has already committed the row -- the endpoint must
    # recover by re-fetching that row rather than raising a 500.
    existing = ActionRecord(
        id=uuid.uuid4(),
        run_id=run_id,
        type="export_excel",
        destination="download",
        status="completed",
        idempotency_key="key-1",
        approved_by="result_owner",
        rejection_reason=None,
        created_at=dt.datetime.now(dt.UTC),
    )
    backend.actions[(run_id, "key-1")] = existing
    calls: list[int] = []

    async def _get_returns_none_once(
        session: object, r: uuid.UUID, key: str
    ) -> ActionRecord | None:
        if not calls:
            calls.append(1)
            return None
        return backend.actions.get((r, key))

    monkeypatch.setattr(actions_module, "get_action_by_idempotency_key", _get_returns_none_once)

    response = client.post(
        f"/api/v1/runs/{run_id}/actions",
        json={"type": "export_excel", "idempotency_key": "key-1"},
    )

    assert response.status_code == 200
    assert response.headers["X-Action-Id"] == str(existing.id)


def test_blank_idempotency_key_is_rejected(client: TestClient, backend: _FakeBackend) -> None:
    run_id = uuid.uuid4()
    backend.runs[run_id] = _snapshot(run_id)

    response = client.post(
        f"/api/v1/runs/{run_id}/actions",
        json={"type": "export_excel", "idempotency_key": "   "},
    )

    assert response.status_code == 422
