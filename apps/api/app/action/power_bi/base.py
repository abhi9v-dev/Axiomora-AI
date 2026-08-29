"""PowerBIAdapter interface: the only way the rest of the app talks to
Power BI (ADR 0002: provider interfaces for external dependencies, the
same pattern as app.llm.base.LLMProvider and
app.embeddings.base.EmbeddingProvider).

Only the two feature-flagged operations from docs/07_SECURITY_GOVERNANCE.md's
action policy table are modeled here -- "create Power BI push rows" and
"trigger dataset refresh". "Replace dataset/report" is prohibited in the
MVP (the table's "Not available"), so no adapter method exists for it;
app.action.policy rejects that action type before any adapter is ever
consulted.

The LLM and the orchestrator never call an adapter directly or hold its
credentials -- only app.api.actions does, after app.action.policy has
already approved the request (CLAUDE.md: "the language model never
receives credentials or direct database/action access").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class PowerBIPushResult:
    dataset_id: str
    table_name: str
    rows_pushed: int


@dataclass
class PowerBIRefreshResult:
    dataset_id: str
    refresh_request_id: str


class PowerBIAdapter(Protocol):
    async def push_rows(
        self, *, dataset_id: str, table_name: str, rows: list[dict[str, object]]
    ) -> PowerBIPushResult:
        """Append rows to an existing Power BI push/streaming dataset table.
        Never replaces or deletes existing rows."""
        ...

    async def refresh_dataset(self, *, dataset_id: str) -> PowerBIRefreshResult:
        """Trigger Power BI to reload a dataset from its configured source."""
        ...
