from __future__ import annotations

import pytest

from app.insight.agent import MAX_INSIGHT_RETRIES, InsightGenerationError, generate_insight
from app.insight.schema import InsightOutput
from app.llm.fake import FakeLLMProvider
from app.validator.schema import QueryResult

_RESULT = QueryResult(
    columns=["department_name", "quarter", "median_hold_hrs"],
    rows=[
        ["Buyer", "Q1", 9.5],
        ["Buyer", "Q2", 27.4],
    ],
    row_count=2,
    truncated=False,
)

_GROUNDED_RESPONSE = (
    '{"headline": "Buyer median hold time rose sharply in Q2", '
    '"narrative": "The increase followed a spike in Supplier Compliance Review tasks.", '
    '"claims": [{"text": "Median hold time moved from 9.5 hours to 27.4 hours", '
    '"evidence": ["result:r1:c3", "result:r2:c3"]}], '
    '"chart": {"type": "bar", "x": "quarter", "y": "median_hold_hrs"}}'
)

_UNGROUNDED_RESPONSE = (
    '{"headline": "h", "narrative": "n", '
    '"claims": [{"text": "Median hold time reached 99.9 hours", '
    '"evidence": ["result:r2:c3"]}], "chart": null}'
)


async def test_grounded_response_parses_into_insight_output() -> None:
    provider = FakeLLMProvider()
    provider.register("hold time spike", _GROUNDED_RESPONSE)

    result = await generate_insight(
        provider, question="Why did hold time spike in Q2?", result=_RESULT
    )

    assert isinstance(result, InsightOutput)
    assert result.claims[0].evidence == ["result:r1:c3", "result:r2:c3"]
    assert len(provider.calls) == 1


async def test_single_llm_call_receives_delimited_prompts_with_cell_ids() -> None:
    provider = FakeLLMProvider()
    provider.register("hold time spike", _GROUNDED_RESPONSE)

    await generate_insight(provider, question="Why did hold time spike in Q2?", result=_RESULT)

    system, user = provider.calls[0]
    assert "RESULT_DATA" in system
    assert "result:r1:c3" in system or "c3=median_hold_hrs" in system
    assert "USER_QUESTION" in user


async def test_malformed_json_then_valid_response_succeeds_on_retry() -> None:
    provider = FakeLLMProvider()
    provider.register("stuck projects", "this is not json", _GROUNDED_RESPONSE)

    result = await generate_insight(provider, question="stuck projects question", result=_RESULT)

    assert isinstance(result, InsightOutput)
    assert len(provider.calls) == 2
    _, second_user_prompt = provider.calls[1]
    assert "FORMAT_CORRECTION" in second_user_prompt


async def test_ungrounded_claim_then_grounded_response_succeeds_on_retry() -> None:
    provider = FakeLLMProvider()
    provider.register("bad claim", _UNGROUNDED_RESPONSE, _GROUNDED_RESPONSE)

    result = await generate_insight(provider, question="bad claim question", result=_RESULT)

    assert result.claims[0].evidence == ["result:r1:c3", "result:r2:c3"]
    assert len(provider.calls) == 2
    _, second_user_prompt = provider.calls[1]
    assert "FORMAT_CORRECTION" in second_user_prompt
    assert "99.9" in second_user_prompt


async def test_two_ungrounded_responses_raise_after_max_retries() -> None:
    provider = FakeLLMProvider()
    provider.register("always ungrounded", _UNGROUNDED_RESPONSE, _UNGROUNDED_RESPONSE)

    with pytest.raises(InsightGenerationError):
        await generate_insight(provider, question="always ungrounded question", result=_RESULT)

    assert len(provider.calls) == MAX_INSIGHT_RETRIES + 1


async def test_empty_result_short_circuits_without_calling_the_llm() -> None:
    provider = FakeLLMProvider()
    empty = QueryResult(columns=["a"], rows=[], row_count=0, truncated=False)

    result = await generate_insight(provider, question="anything", result=empty)

    assert result.claims == []
    assert "no data" in result.headline.lower() or "no rows" in result.narrative.lower()
    assert len(provider.calls) == 0
