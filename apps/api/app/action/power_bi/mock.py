"""Deterministic, zero-cost PowerBIAdapter for development, tests and
demos -- the "mock adapter" docs/10_IMPLEMENTATION_ROADMAP.md's Phase 8
entry calls for, and what POWER_BI_ADAPTER=mock (the default) selects.

Records every call in-memory so tests can assert exactly what would have
been sent to the real Power BI REST API, without a tenant, a network call
or any cost -- the same role FakeLLMProvider plays for LLMProvider.
Always succeeds; PowerBIRestAdapter is the only adapter that can raise
PowerBIAdapterError, matching a real dependency's actual failure modes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.action.power_bi.base import PowerBIPushResult, PowerBIRefreshResult


@dataclass
class MockPowerBIAdapter:
    pushed_calls: list[tuple[str, str, list[dict[str, object]]]] = field(default_factory=list)
    refresh_calls: list[str] = field(default_factory=list)

    async def push_rows(
        self, *, dataset_id: str, table_name: str, rows: list[dict[str, object]]
    ) -> PowerBIPushResult:
        self.pushed_calls.append((dataset_id, table_name, rows))
        return PowerBIPushResult(
            dataset_id=dataset_id, table_name=table_name, rows_pushed=len(rows)
        )

    async def refresh_dataset(self, *, dataset_id: str) -> PowerBIRefreshResult:
        self.refresh_calls.append(dataset_id)
        return PowerBIRefreshResult(
            dataset_id=dataset_id, refresh_request_id=f"mock-refresh-{uuid.uuid4()}"
        )
