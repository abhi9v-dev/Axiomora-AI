from __future__ import annotations

import pytest

from app.catalog.schema import RetrievalResult
from app.llm.fake import FakeLLMProvider
from app.nl2sql.agent import MAX_FORMAT_RETRIES, NL2SQLGenerationError, generate_sql
from app.nl2sql.schema import NL2SQLOutput

_CONTEXT = [
    RetrievalResult(
        chunk_id=1,
        document_id=1,
        kind="table",
        object_name="analytics.v_task_lifecycle",
        title="View: analytics.v_task_lifecycle",
        content="one row per task, with assignee_hold_hrs and department_name",
        score=0.9,
        citation="catalog:table:analytics.v_task_lifecycle:chunk:0",
    ),
    RetrievalResult(
        chunk_id=2,
        document_id=2,
        kind="glossary_term",
        object_name="hold_time",
        title="Glossary: hold time",
        content="Hold time is claim-to-completion duration.",
        score=0.7,
        citation="catalog:glossary_term:hold_time:chunk:0",
    ),
]

_VALID_RESPONSE = (
    '{"sql": "SELECT department_name, percentile_cont(0.5) WITHIN GROUP '
    "(ORDER BY assignee_hold_hrs) AS median_hold_hrs FROM analytics.v_task_lifecycle "
    "WHERE department_name = 'Buyer' GROUP BY 1\", "
    '"dialect": "postgres", '
    '"referenced_objects": ["analytics.v_task_lifecycle"], '
    '"assumptions": ["Q2 refers to the latest complete calendar Q2"], '
    '"parameters": {"department_name": "Buyer"}, '
    '"confidence": 0.9}'
)


async def test_valid_response_parses_into_nl2sql_output() -> None:
    provider = FakeLLMProvider()
    provider.register("hold time spike", _VALID_RESPONSE)

    result = await generate_sql(
        provider,
        question="Why did median task hold time spike for the Buyer department in Q2?",
        dialect="postgres",
        retrieved_context=_CONTEXT,
    )

    assert isinstance(result, NL2SQLOutput)
    assert result.dialect == "postgres"
    assert "analytics.v_task_lifecycle" in result.referenced_objects
    assert result.parameters == {"department_name": "Buyer"}
    assert result.confidence == pytest.approx(0.9)
    assert len(provider.calls) == 1


async def test_single_llm_call_receives_delimited_prompts() -> None:
    provider = FakeLLMProvider()
    provider.register("hold time spike", _VALID_RESPONSE)

    await generate_sql(
        provider,
        question="Why did median task hold time spike for the Buyer department in Q2?",
        dialect="postgres",
        retrieved_context=_CONTEXT,
    )

    system, user = provider.calls[0]
    assert "RETRIEVED_SCHEMA_CONTEXT" in system
    assert "analytics.v_task_lifecycle" in system
    assert "USER_QUESTION" in user


async def test_malformed_json_then_valid_response_succeeds_on_retry() -> None:
    provider = FakeLLMProvider()
    provider.register("stuck projects", "this is not json", _VALID_RESPONSE)

    result = await generate_sql(
        provider,
        question="How many stuck projects are there?",
        dialect="postgres",
        retrieved_context=_CONTEXT,
    )

    assert isinstance(result, NL2SQLOutput)
    assert len(provider.calls) == 2
    # The retry prompt must reference the original question and explain
    # what went wrong, not silently retry the identical prompt.
    _, second_user_prompt = provider.calls[1]
    assert "FORMAT_CORRECTION" in second_user_prompt
    assert "stuck projects" in second_user_prompt


async def test_response_missing_required_field_triggers_retry() -> None:
    """A syntactically valid JSON object that fails schema validation
    (missing `confidence`) must be treated as malformed, same as bad JSON."""
    provider = FakeLLMProvider()
    missing_confidence = '{"sql": "SELECT 1", "dialect": "postgres"}'
    provider.register("missing field", missing_confidence, _VALID_RESPONSE)

    result = await generate_sql(
        provider,
        question="missing field question",
        dialect="postgres",
        retrieved_context=_CONTEXT,
    )

    assert isinstance(result, NL2SQLOutput)
    assert len(provider.calls) == 2


async def test_two_malformed_responses_raise_after_max_retries() -> None:
    provider = FakeLLMProvider()
    provider.register("always broken", "not json", "still not json")

    with pytest.raises(NL2SQLGenerationError):
        await generate_sql(
            provider,
            question="always broken question",
            dialect="postgres",
            retrieved_context=_CONTEXT,
        )

    assert len(provider.calls) == MAX_FORMAT_RETRIES + 1


async def test_confidence_out_of_range_is_rejected_as_malformed() -> None:
    provider = FakeLLMProvider()
    out_of_range = _VALID_RESPONSE.replace('"confidence": 0.9', '"confidence": 1.5')
    provider.register("bad confidence", out_of_range, _VALID_RESPONSE)

    result = await generate_sql(
        provider,
        question="bad confidence question",
        dialect="postgres",
        retrieved_context=_CONTEXT,
    )

    assert result.confidence == pytest.approx(0.9)
    assert len(provider.calls) == 2


async def test_no_retrieved_context_still_produces_a_low_confidence_response() -> None:
    provider = FakeLLMProvider()
    low_confidence = (
        '{"sql": "SELECT 1", "dialect": "postgres", "referenced_objects": [], '
        '"assumptions": ["no schema context was available"], "parameters": {}, '
        '"confidence": 0.1}'
    )
    provider.register("no context available", low_confidence)

    result = await generate_sql(
        provider,
        question="no context available question",
        dialect="postgres",
        retrieved_context=[],
    )

    assert result.confidence < 0.5
    assert result.referenced_objects == []
