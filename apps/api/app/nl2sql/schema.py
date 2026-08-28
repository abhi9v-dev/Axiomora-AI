"""Versioned NL2SQL output contract (docs/06_DATA_MODEL_API_CONTRACTS.md).

Every NL2SQL response -- from any provider -- is validated against this
model before the rest of the system ever sees it. `parameters` is
restricted to primitive scalars (not arbitrary JSON) so it binds cleanly
as SQL parameters in Phase 4's Validator Agent.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

ParameterValue = str | int | float | bool


class NL2SQLOutput(BaseModel):
    sql: str
    dialect: str = "postgres"
    referenced_objects: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    parameters: dict[str, ParameterValue] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
