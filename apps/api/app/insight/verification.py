"""Claim-verification pass (CLAUDE.md: "numeric narrative claims require
result-cell evidence references"; docs/08_TEST_EVAL_ACCEPTANCE.md AT-06:
"narrative adds unsupported number -> evidence binding rejects response").

Scoped to `InsightOutput.claims` -- the structured, evidence-bound
statements -- rather than the free-form `headline`/`narrative` prose, which
may legitimately summarize or round a claim's numbers (docs/06's own
example headline, "increased 18 hours", is a rounded delta of the claim's
exact 9.5/27.4 figures, not a literal cell value). Every number that
appears in a claim's text must equal a value resolved from that same
claim's own evidence cell(s); a claim with numbers but no evidence, or with
an evidence reference that doesn't resolve, is a violation. This is
deterministic, Python-side verification -- never trust the model's own
claim that a citation is valid (CLAUDE.md: "keep arithmetic in SQL/Python,
not the model").
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from app.insight.schema import InsightOutput
from app.insight.serialization import CellReferenceError, resolve_cell
from app.validator.schema import QueryResult

# A run of digits (with optional thousands separators and a decimal part)
# not directly touching a letter or another digit on either side -- this
# excludes things like the "2" in "Q2" (preceded by a letter) while still
# matching "18%" (a percent sign isn't alphanumeric) and "1,234.5".
_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9])-?\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])")


@dataclass
class VerificationResult:
    ok: bool
    violations: list[str] = field(default_factory=list)


def extract_numbers(text: str) -> list[float]:
    return [float(match.replace(",", "")) for match in _NUMBER_PATTERN.findall(text)]


def _matches_any(number: float, values: list[object]) -> bool:
    for value in values:
        try:
            if math.isclose(number, float(value), rel_tol=1e-6, abs_tol=1e-6):  # type: ignore[arg-type]
                return True
        except (TypeError, ValueError):
            continue
    return False


def verify_claims(result: QueryResult, output: InsightOutput) -> VerificationResult:
    violations: list[str] = []

    for idx, claim in enumerate(output.claims, start=1):
        numbers = extract_numbers(claim.text)
        if not numbers:
            continue  # a non-numeric claim needs no evidence

        if not claim.evidence:
            violations.append(
                f"Claim {idx} ('{claim.text}') states a number but cites no evidence."
            )
            continue

        resolved: list[object] = []
        for ref in claim.evidence:
            try:
                resolved.append(resolve_cell(result, ref))
            except CellReferenceError as exc:
                violations.append(f"Claim {idx}: {exc}")

        for number in numbers:
            if not _matches_any(number, resolved):
                violations.append(
                    f"Claim {idx} ('{claim.text}') states {number}, which does not match any "
                    f"value in its cited evidence {claim.evidence}."
                )

    return VerificationResult(ok=not violations, violations=violations)
