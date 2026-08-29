"""Repair-loop and Insight-wiring coordination tests for
app.pipeline.answer_question.

app.validator.agent.validate_and_execute and app.insight.agent.generate_insight
are both replaced with scripted stubs (via monkeypatch) rather than exercised
for real here -- they need a live warehouse connection / are covered in their
own detail by test_validator_integration.py and test_insight_agent.py. This
file verifies the *coordination logic* itself: how many NL2SQL calls happen,
when the repair loop stops, what feedback gets fed back on a retry, and
whether/how Insight generation gets invoked once validation settles.
"""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.catalog.schema import RetrievalResult
from app.insight.agent import InsightGenerationError
from app.insight.schema import InsightOutput
from app.llm.fake import FakeLLMProvider
from app.nl2sql.schema import NL2SQLOutput
from app.pipeline import PipelineError, PipelineResult, answer_question
from app.validator.schema import QueryResult, ValidationCheck, ValidatorOutput

_CONTEXT: list[RetrievalResult] = []
# validate_and_execute is stubbed in every test here, so no real engine is
# ever used -- this stands in for the AsyncEngine parameter type-wise only.
_UNUSED_ENGINE = cast(AsyncEngine, object())

_VALID_RESPONSE = (
    '{"sql": "SELECT 1", "dialect": "postgres", "referenced_objects": [], '
    '"assumptions": [], "parameters": {}, "confidence": 0.9}'
)

_SAMPLE_RESULT = QueryResult(
    columns=["median_hold_hrs"], rows=[[27.4]], row_count=1, truncated=False
)


def _pass_output(result: QueryResult | None = None) -> ValidatorOutput:
    return ValidatorOutput(
        status="pass",
        checks=[ValidationCheck(name="sql_policy", status="pass", details="ok")],
        repairable=False,
        result=result if result is not None else _SAMPLE_RESULT,
    )


def _repairable_fail_output(feedback: str = "fix your SQL") -> ValidatorOutput:
    return ValidatorOutput(
        status="fail",
        checks=[ValidationCheck(name="sql_policy", status="fail", details=feedback)],
        repairable=True,
        feedback=feedback,
    )


def _terminal_fail_output() -> ValidatorOutput:
    return ValidatorOutput(
        status="fail",
        checks=[ValidationCheck(name="execution", status="fail", details="unfixable")],
        repairable=False,
        feedback="this cannot be repaired",
    )


class _ScriptedValidator:
    """Stand-in for app.validator.agent.validate_and_execute: returns each
    queued ValidatorOutput in order and records every call it received."""

    def __init__(self, outputs: list[ValidatorOutput]) -> None:
        self._outputs = list(outputs)
        self.calls: list[NL2SQLOutput] = []

    async def __call__(
        self, engine: object, nl2sql_output: NL2SQLOutput, *, timeout_ms: int, row_limit: int
    ) -> ValidatorOutput:
        self.calls.append(nl2sql_output)
        return self._outputs.pop(0)


class _StubInsight:
    """Stand-in for app.insight.agent.generate_insight: records every call
    it received and either returns a fixed InsightOutput or raises a fixed
    error, so pipeline tests can assert on *whether/how* Insight generation
    was invoked without depending on real LLM parsing/verification (that's
    test_insight_agent.py's job)."""

    def __init__(self, output: InsightOutput | None = None, error: Exception | None = None) -> None:
        self._output = output if output is not None else InsightOutput(headline="h", narrative="n")
        self._error = error
        self.calls: list[tuple[str, QueryResult]] = []

    async def __call__(
        self, llm_provider: object, *, question: str, result: QueryResult
    ) -> InsightOutput:
        self.calls.append((question, result))
        if self._error is not None:
            raise self._error
        return self._output


async def _run(
    monkeypatch: pytest.MonkeyPatch,
    provider: FakeLLMProvider,
    validator: _ScriptedValidator,
    *,
    max_repairs: int = 2,
    insight: _StubInsight | None = None,
) -> PipelineResult:
    monkeypatch.setattr("app.pipeline.validate_and_execute", validator)
    monkeypatch.setattr("app.pipeline.generate_insight", insight or _StubInsight())
    return await answer_question(
        provider,
        engine=_UNUSED_ENGINE,
        question="Why did hold time spike?",
        dialect="postgres",
        retrieved_context=_CONTEXT,
        max_repairs=max_repairs,
        timeout_ms=10_000,
        row_limit=5_000,
    )


async def test_first_attempt_passing_stops_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_RESPONSE)
    validator = _ScriptedValidator([_pass_output()])

    result = await _run(monkeypatch, provider, validator)

    assert result.validator_output.status == "pass"
    assert result.attempts == 1
    assert len(validator.calls) == 1
    assert len(provider.calls) == 1


async def test_repairable_failure_then_success_uses_two_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_RESPONSE, _VALID_RESPONSE)
    validator = _ScriptedValidator([_repairable_fail_output("bad table"), _pass_output()])

    result = await _run(monkeypatch, provider, validator)

    assert result.validator_output.status == "pass"
    assert result.attempts == 2
    assert len(provider.calls) == 2
    # The second NL2SQL call must carry the validator's feedback forward.
    _, second_user_prompt = provider.calls[1]
    assert "VALIDATOR_FEEDBACK" in second_user_prompt
    assert "bad table" in second_user_prompt


async def test_exhausts_max_repairs_and_returns_final_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_RESPONSE, _VALID_RESPONSE, _VALID_RESPONSE)
    validator = _ScriptedValidator(
        [_repairable_fail_output("x"), _repairable_fail_output("y"), _repairable_fail_output("z")]
    )

    result = await _run(monkeypatch, provider, validator, max_repairs=2)

    assert result.validator_output.status == "fail"
    assert result.attempts == 3  # 1 initial + 2 repairs, then give up
    assert len(validator.calls) == 3


async def test_non_repairable_failure_stops_immediately_even_with_repairs_left(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_RESPONSE)
    validator = _ScriptedValidator([_terminal_fail_output()])

    result = await _run(monkeypatch, provider, validator, max_repairs=2)

    assert result.validator_output.status == "fail"
    assert result.attempts == 1
    assert len(validator.calls) == 1


async def test_zero_max_repairs_allows_exactly_one_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_RESPONSE)
    validator = _ScriptedValidator([_repairable_fail_output()])

    result = await _run(monkeypatch, provider, validator, max_repairs=0)

    assert result.attempts == 1
    assert len(validator.calls) == 1


async def test_negative_max_repairs_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FakeLLMProvider()
    validator = _ScriptedValidator([])
    monkeypatch.setattr("app.pipeline.validate_and_execute", validator)

    with pytest.raises(ValueError, match="max_repairs"):
        await answer_question(
            provider,
            engine=_UNUSED_ENGINE,
            question="q",
            dialect="postgres",
            retrieved_context=_CONTEXT,
            max_repairs=-1,
            timeout_ms=10_000,
            row_limit=5_000,
        )


async def test_nl2sql_generation_failure_raises_pipeline_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FakeLLMProvider with nothing registered returns "{}" (missing
    required fields), which fails NL2SQLOutput validation on every retry
    -- this must surface as PipelineError, not an unhandled exception from
    inside app.nl2sql.agent."""
    provider = FakeLLMProvider()  # no rules registered -> always "{}"
    validator = _ScriptedValidator([])

    with pytest.raises(PipelineError):
        await _run(monkeypatch, provider, validator)

    assert len(validator.calls) == 0  # never reached the validator at all


async def test_validator_pass_calls_insight_agent_with_the_validated_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_RESPONSE)
    result = QueryResult(columns=["x"], rows=[[1]], row_count=1, truncated=False)
    validator = _ScriptedValidator([_pass_output(result)])
    expected_insight = InsightOutput(headline="Buyer hold time rose", narrative="n")
    insight = _StubInsight(expected_insight)

    pipeline_result = await _run(monkeypatch, provider, validator, insight=insight)

    assert pipeline_result.insight_output is expected_insight
    assert pipeline_result.insight_error is None
    assert len(insight.calls) == 1
    called_question, called_result = insight.calls[0]
    assert called_question == "Why did hold time spike?"
    assert called_result is result


async def test_validator_terminal_failure_does_not_call_insight_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLAUDE.md: "failed validation blocks the Insight Agent"."""
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_RESPONSE)
    validator = _ScriptedValidator([_terminal_fail_output()])
    insight = _StubInsight()

    pipeline_result = await _run(monkeypatch, provider, validator, insight=insight)

    assert pipeline_result.insight_output is None
    assert pipeline_result.insight_error is None
    assert len(insight.calls) == 0


async def test_validator_failure_exhausting_repairs_does_not_call_insight_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_RESPONSE, _VALID_RESPONSE, _VALID_RESPONSE)
    validator = _ScriptedValidator(
        [_repairable_fail_output("x"), _repairable_fail_output("y"), _repairable_fail_output("z")]
    )
    insight = _StubInsight()

    pipeline_result = await _run(monkeypatch, provider, validator, max_repairs=2, insight=insight)

    assert pipeline_result.insight_output is None
    assert len(insight.calls) == 0


async def test_insight_generation_failure_is_captured_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Insight generation failing (e.g. a model outage) must not discard the
    already-validated SQL result -- docs/03_ARCHITECTURE.md's failure
    handling: "model outage: preserve run state and allow retry"."""
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_RESPONSE)
    validator = _ScriptedValidator([_pass_output()])
    insight = _StubInsight(error=InsightGenerationError("model outage"))

    pipeline_result = await _run(monkeypatch, provider, validator, insight=insight)

    assert pipeline_result.insight_output is None
    assert pipeline_result.insight_error == "model outage"
    assert pipeline_result.validator_output.status == "pass"
