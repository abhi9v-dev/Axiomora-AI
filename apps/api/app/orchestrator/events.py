"""In-process SSE fan-out for live run progress
(docs/05_FRONTEND_UX.md: "use server-sent events for progress; reconnect
by run_id").

Each run gets one `RunEventBus`: every RunSnapshot the orchestrator
publishes is kept in a buffer (so a client that connects -- or reconnects
-- after the run has already progressed still sees every event from the
start) and fanned out live to every currently-subscribed queue. A subscriber
that sees a terminal-status snapshot (READY/NEEDS_CLARIFICATION/FAILED/
CANCELLED) stops iterating on its own; the bus itself keeps its buffer for
the life of the process so a late reconnect still works.

Single-process only -- buses live in this module's process memory, not a
shared store, so this would need to move to a real pub/sub (e.g. Postgres
LISTEN/NOTIFY or Redis) before running behind more than one API worker.
Acceptable for this project's single-instance MVP deployment (Phase 9);
documented here rather than silently assumed.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

from app.orchestrator.schema import TERMINAL_STATUSES, RunSnapshot


class RunEventBus:
    def __init__(self) -> None:
        self._buffer: list[RunSnapshot] = []
        self._subscribers: list[asyncio.Queue[RunSnapshot]] = []
        self._lock = asyncio.Lock()

    async def publish(self, snapshot: RunSnapshot) -> None:
        async with self._lock:
            self._buffer.append(snapshot)
            for queue in self._subscribers:
                queue.put_nowait(snapshot)

    async def subscribe(self) -> AsyncIterator[RunSnapshot]:
        queue: asyncio.Queue[RunSnapshot] = asyncio.Queue()
        async with self._lock:
            for snapshot in self._buffer:
                queue.put_nowait(snapshot)
            self._subscribers.append(queue)
        try:
            while True:
                snapshot = await queue.get()
                yield snapshot
                if snapshot.status in TERMINAL_STATUSES:
                    return
        finally:
            async with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)


_BUSES: dict[uuid.UUID, RunEventBus] = {}


def get_event_bus(run_id: uuid.UUID) -> RunEventBus:
    """Returns the same bus for a given run_id for the life of the process,
    creating it on first use (by the orchestrator when the run starts, or
    by an SSE subscriber that connects first -- either order works)."""
    bus = _BUSES.get(run_id)
    if bus is None:
        bus = RunEventBus()
        _BUSES[run_id] = bus
    return bus
