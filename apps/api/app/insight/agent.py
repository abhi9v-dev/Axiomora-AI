"""The Insight Agent: a validated, already-executed query result ->
a claim-grounded narrative (docs/06_DATA_MODEL_API_CONTRACTS.md's Insight
output contract).

Architecture invariants this module upholds:
- Never receives an unvalidated result -- callers (app.pipeline) only
  invoke this after app.validator.agent.validate_and_execute has passed
  (CLAUDE.md: "failed validation blocks the Insight Agent").
- An empty result never reaches the model at all: docs/08's AT-05 ("result
  is empty -> explain no data; do not invent insight") is enforced
  deterministically in Python, not by trusting the model to behave.
- Every non-empty response is independently claim-verified
  (app.insight.verification) before being trusted; a response that fails
  parsing or verification gets exactly one corrective retry, then raises
  rather than returning anything ungrounded.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.insight.prompts import build_system_prompt, build_user_prompt
from app.insight.schema import InsightOutput
from app.insight.verification import verify_claims
from app.llm.base import LLMProvider
from app.validator.schema import QueryResult

# One corrective retry, shared between "didn't parse" and "failed claim
# verification" -- matching app.nl2sql.agent's MAX_FORMAT_RETRIES budget.
MAX_INSIGHT_RETRIES = 1

_NO_DATA_OUTPUT = InsightOutput(
    headline="No data found for this question.",
    narrative=(
        "The query returned no rows, so there is nothing to report. This may mean the "
        "filters were too narrow, or that no matching activity occurred in the requested "
        "period."
    ),
    claims=[],
    chart=None,
)


class InsightGenerationError(Exception):
    """Raised when the response still doesn't match InsightOutput, or still
    fails claim verification, after the retry budget is exhausted."""


def _parse_response(raw: str) -> InsightOutput:
    data = json.loads(raw)  # raises json.JSONDecodeError on non-JSON text
    return InsightOutput.model_validate(data)  # raises pydantic.ValidationError


def _build_correction_prompt(original_user_prompt: str, problem: str) -> str:
    return (
        f"{original_user_prompt}\n\n"
        "<<<FORMAT_CORRECTION>>>\n"
        f"Your previous response was rejected: {problem}. Respond again with ONLY the "
        "required JSON object, no other text, and make sure every numeric claim's "
        "evidence cites a cell that actually contains that exact number.\n"
        "<<<END_FORMAT_CORRECTION>>>"
    )


async def generate_insight(
    llm_provider: LLMProvider,
    *,
    question: str,
    result: QueryResult,
) -> InsightOutput:
    if result.row_count == 0:
        return _NO_DATA_OUTPUT

    system = build_system_prompt(result=result)
    user = build_user_prompt(question)

    last_problem: str | None = None
    for attempt in range(MAX_INSIGHT_RETRIES + 1):
        if attempt == 0:
            prompt_user = user
        else:
            assert last_problem is not None  # set on every prior iteration's branch
            prompt_user = _build_correction_prompt(user, last_problem)

        raw = await llm_provider.complete(system=system, user=prompt_user)
        try:
            output = _parse_response(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_problem = f"the response could not be parsed ({exc})"
            continue

        verification = verify_claims(result, output)
        if verification.ok:
            return output
        last_problem = "; ".join(verification.violations)

    raise InsightGenerationError(
        f"Insight response did not pass validation/verification after "
        f"{MAX_INSIGHT_RETRIES + 1} attempt(s): {last_problem}"
    )
