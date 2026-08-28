"""Versioned Validator contracts (docs/06_DATA_MODEL_API_CONTRACTS.md).

`ValidatorOutput` is the top-level result: `status` pass/fail, a list of
individual named `checks`, whether a failure is `repairable` (worth
retrying NL2SQL with feedback) and, if so, the `feedback` text to send
back. A failed Must check blocks the Insight Agent (Phase 5) and the
Action Agent (Phase 7) -- see CLAUDE.md's architecture invariants.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ValidationCheck(BaseModel):
    name: str
    status: Literal["pass", "fail", "warning"]
    details: str


class QueryResult(BaseModel):
    """A validated, executed query's results -- always from the read-only
    warehouse role, always row-limited."""

    columns: list[str]
    rows: list[list[object]]
    row_count: int
    truncated: bool


class ValidatorOutput(BaseModel):
    status: Literal["pass", "fail"]
    checks: list[ValidationCheck]
    repairable: bool
    feedback: str | None = None
    result: QueryResult | None = None
