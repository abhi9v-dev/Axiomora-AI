"""app.orchestrator.events.RunEventBus: buffered replay + live fan-out for
SSE (docs/05_FRONTEND_UX.md: "reconnect by run_id").
"""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid

from app.orchestrator.events import RunEventBus, get_event_bus
from app.orchestrator.schema import RunSnapshot, RunStatus


def _snapshot(status: RunStatus, run_id: uuid.UUID | None = None) -> RunSnapshot:
    now = dt.datetime.now(dt.UTC)
    return RunSnapshot(
        run_id=run_id or uuid.uuid4(),
        tenant_id="default",
        source_id="marketplace_demo",
        question="Why did hold time spike?",
        status=status,
        created_at=now,
        updated_at=now,
    )


async def test_subscriber_replays_events_published_before_it_connected() -> None:
    bus = RunEventBus()
    await bus.publish(_snapshot("RECEIVED"))
    await bus.publish(_snapshot("RETRIEVING"))

    received = []
    async for snapshot in bus.subscribe():
        received.append(snapshot.status)
        if len(received) == 2:
            break

    assert received == ["RECEIVED", "RETRIEVING"]


async def test_subscriber_receives_events_published_after_it_connected() -> None:
    bus = RunEventBus()
    received: list[str] = []

    async def consume() -> None:
        async for snapshot in bus.subscribe():
            received.append(snapshot.status)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)  # let the subscriber register before we publish
    await bus.publish(_snapshot("RECEIVED"))
    await bus.publish(_snapshot("READY"))  # terminal -- consume() should return on its own
    await asyncio.wait_for(task, timeout=1)

    assert received == ["RECEIVED", "READY"]


async def test_multiple_subscribers_each_get_every_event() -> None:
    bus = RunEventBus()
    first: list[str] = []
    second: list[str] = []

    async def consume(sink: list[str]) -> None:
        async for snapshot in bus.subscribe():
            sink.append(snapshot.status)

    t1 = asyncio.create_task(consume(first))
    t2 = asyncio.create_task(consume(second))
    await asyncio.sleep(0)
    await bus.publish(_snapshot("FAILED"))  # terminal
    await asyncio.wait_for(t1, timeout=1)
    await asyncio.wait_for(t2, timeout=1)

    assert first == ["FAILED"]
    assert second == ["FAILED"]


async def test_reconnect_after_terminal_status_still_replays_full_history() -> None:
    bus = RunEventBus()
    await bus.publish(_snapshot("RECEIVED"))
    await bus.publish(_snapshot("READY"))

    received = [snapshot.status async for snapshot in bus.subscribe()]

    assert received == ["RECEIVED", "READY"]


async def test_get_event_bus_returns_the_same_instance_for_a_run_id() -> None:
    run_id = uuid.uuid4()

    assert get_event_bus(run_id) is get_event_bus(run_id)


async def test_get_event_bus_returns_different_instances_for_different_runs() -> None:
    assert get_event_bus(uuid.uuid4()) is not get_event_bus(uuid.uuid4())
