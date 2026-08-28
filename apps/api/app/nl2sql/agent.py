"""The NL2SQL agent: question + retrieved context -> structured SQL draft.

Architecture invariants this module upholds:
- Never executes SQL (that's the Validator Agent, Phase 4) and never
  receives credentials -- only the already-retrieved catalog context and
  the question text.
- Every response is validated against the versioned NL2SQLOutput contract;
  a response that doesn't parse gets exactly one corrective retry and is
  never trusted as free-form control instructions
  (docs/06_DATA_MODEL_API_CONTRACTS.md).
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.catalog.schema import RetrievalResult
from app.llm.base import LLMProvider
from app.nl2sql.prompts import build_system_prompt, build_user_prompt
from app.nl2sql.schema import NL2SQLOutput

# docs/06_DATA_MODEL_API_CONTRACTS.md: "Invalid responses are retried once
# for formatting" -- one retry total, not a repair/validation loop (that's
# Phase 4's separate, SQL-policy-driven repair loop, capped independently).
MAX_FORMAT_RETRIES = 1


class NL2SQLGenerationError(Exception):
    """Raised when the response still doesn't match NL2SQLOutput after the
    formatting retry."""


def _parse_response(raw: str) -> NL2SQLOutput:
    data = json.loads(raw)  # raises json.JSONDecodeError on non-JSON text
    return NL2SQLOutput.model_validate(data)  # raises pydantic.ValidationError


def _build_correction_prompt(original_user_prompt: str, error: Exception) -> str:
    return (
        f"{original_user_prompt}\n\n"
        "<<<FORMAT_CORRECTION>>>\n"
        f"Your previous response could not be parsed: {error}. Respond again "
        "with ONLY the required JSON object, no other text.\n"
        "<<<END_FORMAT_CORRECTION>>>"
    )


async def generate_sql(
    llm_provider: LLMProvider,
    *,
    question: str,
    dialect: str,
    retrieved_context: list[RetrievalResult],
) -> NL2SQLOutput:
    system = build_system_prompt(dialect=dialect, retrieved_context=retrieved_context)
    user = build_user_prompt(question)

    last_error: Exception | None = None
    for attempt in range(MAX_FORMAT_RETRIES + 1):
        if attempt == 0:
            prompt_user = user
        else:
            assert last_error is not None  # set on every prior iteration's except branch
            prompt_user = _build_correction_prompt(user, last_error)

        raw = await llm_provider.complete(system=system, user=prompt_user)
        try:
            return _parse_response(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc

    raise NL2SQLGenerationError(
        f"NL2SQL response did not match the contract after "
        f"{MAX_FORMAT_RETRIES + 1} attempt(s): {last_error}"
    )
