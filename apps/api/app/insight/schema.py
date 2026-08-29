"""Versioned Insight output contract (docs/06_DATA_MODEL_API_CONTRACTS.md).

Every Insight response -- from any provider -- is validated against this
model before the rest of the system ever sees it, same pattern as
NL2SQLOutput (app.nl2sql.schema) and ValidatorOutput (app.validator.schema).
`claims` is the mechanism that binds a numeric statement to concrete
result-cell evidence (app.insight.verification); `chart` is optional
because not every result shape suggests a sensible chart (e.g. a single
scalar, or an empty result).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Claim(BaseModel):
    text: str
    evidence: list[str] = Field(default_factory=list)


class ChartSuggestion(BaseModel):
    type: str
    x: str
    y: str


class InsightOutput(BaseModel):
    headline: str
    narrative: str
    claims: list[Claim] = Field(default_factory=list)
    chart: ChartSuggestion | None = None
