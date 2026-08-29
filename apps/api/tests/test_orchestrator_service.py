"""Coordination tests for app.orchestrator.service: the state sequence a
run actually goes through, and when it pauses for clarification, fails or
reaches Insight.

app.catalog.retrieval.search_catalog, app.validator.agent.validate_and_execute
and app.insight.agent.generate_insight are all replaced with scripted stubs
(via monkeypatch) -- each is unit-tested on its own elsewhere
(test_recall_offline.py, test_validator_*.py, test_insight_agent.py) and
two of the three need a live database. app.orchestrator.store is replaced
with an in-memory fake so these tests need no database either; only
FakeLLMProvider does real work, matching test_pipeline.py's approach one
layer down.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.catalog.schema import RetrievalResult
from app.embeddings.base import EmbeddingProvider
from app.insight.agent import InsightGenerationError
from app.insight.schema import InsightOutput
from app.llm.fake import FakeLLMProvider
from app.nl2sql.schema import NL2SQLOutput
from app.orchestrator import service, store
from app.orchestrator.events import get_event_bus
from app.orchestrator.schema import RunSnapshot
from app.orchestrator.service import (
    NotAwaitingClarificationError,
    OrchestratorParams,
    cancel_run,
    create_run,
    execute_run,
    record_clarification,
)
from app.validator.schema import QueryResult, ValidationCheck, ValidatorOutput

_UNUSED_SESSION = cast(AsyncSession, object())
_UNUSED_ENGINE = cast(AsyncEngine, object())
_UNUSED_EMBEDDING = cast(EmbeddingProvider, object())

_CONTEXT = [
    RetrievalResult(
        chunk_id=1,
        document_id=1,
        kind="table",
        object_name="analytics.v_task_lifecycle",
        title="View: analytics.v_task_lifecycle",
        content="hold time by department",
        score=0.9,
        citation="catalog:table:analytics.v_task_lifecycle:chunk:0",
    )
]

_LOW_SCORE_CONTEXT = [
    RetrievalResult(
        chunk_id=1,
        document_id=1,
        kind="table",
        object_name="analytics.v_task_lifecycle",
        title="View: analytics.v_task_lifecycle",
        content="barely related",
        score=0.05,
        citation="catalog:table:analytics.v_task_lifecycle:chunk:0",
    )
]

_VALID_SQL_RESPONSE = (
    '{"sql": "SELECT 1", "dialect": "postgres", "referenced_objects": [], '
    '"assumptions": [], "parameters": {}, "confidence": 0.9}'
)

_LOW_CONFIDENCE_RESPONSE = (
    '{"sql": "SELECT 1", "dialect": "postgres", "referenced_objects": [], '
    '"assumptions": ["Q2 could mean fiscal or calendar quarter"], "parameters": {}, '
    '"confidence": 0.1}'
)

_DEFAULT_PARAMS = OrchestratorParams(
    max_repairs=2,
    timeout_ms=10_000,
    row_limit=5_000,
    retrieval_min_score=0.2,
    nl2sql_min_confidence=0.4,
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


def _repairable_fail(feedback: str = "fix your SQL") -> ValidatorOutput:
    return ValidatorOutput(
        status="fail",
        checks=[ValidationCheck(name="sql_policy", status="fail", details=feedback)],
        repairable=True,
        feedback=feedback,
    )


def _terminal_fail() -> ValidatorOutput:
    return ValidatorOutput(
        status="fail",
        checks=[ValidationCheck(name="execution", status="fail", details="unfixable")],
        repairable=False,
        feedback="this cannot be repaired",
    )


class _FakeStore:
    def __init__(self) -> None:
        self.runs: dict[uuid.UUID, RunSnapshot] = {}

    async def create_run(self, session: object, snapshot: RunSnapshot) -> None:
        self.runs[snapshot.run_id] = snapshot.model_copy(deep=True)

    async def save_run(self, session: object, snapshot: RunSnapshot) -> None:
        self.runs[snapshot.run_id] = snapshot.model_copy(deep=True)

    async def get_run(self, session: object, run_id: uuid.UUID) -> RunSnapshot | None:
        row = self.runs.get(run_id)
        return row.model_copy(deep=True) if row is not None else None


class _ScriptedValidator:
    def __init__(self, outputs: list[ValidatorOutput]) -> None:
        self._outputs = list(outputs)
        self.calls: list[NL2SQLOutput] = []

    async def __call__(
        self, engine: object, nl2sql_output: NL2SQLOutput, *, timeout_ms: int, row_limit: int
    ) -> ValidatorOutput:
        self.calls.append(nl2sql_output)
        return self._outputs.pop(0)


class _StubInsight:
    def __init__(self, output: InsightOutput | None = None, error: Exception | None = None) -> None:
        self._output = output if output is not None else InsightOutput(headline="h", narrative="n")
        self._error = error
        self.calls: list[str] = []

    async def __call__(
        self, llm_provider: object, *, question: str, result: object
    ) -> InsightOutput:
        self.calls.append(question)
        if self._error is not None:
            raise self._error
        return self._output


def _search_catalog_returning(context: list[RetrievalResult]) -> object:
    async def _search(
        session: object, query: str, *, tenant_id: str, source_id: str, embedding_provider: object
    ) -> list[RetrievalResult]:
        return context

    return _search


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    context: list[RetrievalResult] = _CONTEXT,
    validator: _ScriptedValidator | None = None,
    insight: _StubInsight | None = None,
    fake_store: _FakeStore | None = None,
) -> tuple[_FakeStore, _ScriptedValidator, _StubInsight]:
    fake_store = fake_store or _FakeStore()
    monkeypatch.setattr(store, "create_run", fake_store.create_run)
    monkeypatch.setattr(store, "save_run", fake_store.save_run)
    monkeypatch.setattr(store, "get_run", fake_store.get_run)
    monkeypatch.setattr(service, "search_catalog", _search_catalog_returning(context))

    scripted_validator = validator or _ScriptedValidator([_pass_output()])
    monkeypatch.setattr(service, "validate_and_execute", scripted_validator)

    stub_insight = insight or _StubInsight()
    monkeypatch.setattr(service, "generate_insight", stub_insight)

    return fake_store, scripted_validator, stub_insight


async def _new_run(question: str = "Why did hold time spike?") -> RunSnapshot:
    return await create_run(
        session=_UNUSED_SESSION,
        tenant_id="default",
        source_id="marketplace_demo",
        question=question,
    )


async def test_happy_path_reaches_ready_with_insight(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_SQL_RESPONSE)
    snapshot = await _new_run()

    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=get_event_bus(snapshot.run_id),
        snapshot=snapshot,
        effective_question=snapshot.question,
        params=_DEFAULT_PARAMS,
    )

    assert snapshot.status == "READY"
    assert snapshot.insight is not None
    assert snapshot.insight_error is None
    assert len(snapshot.attempts) == 1
    assert snapshot.attempts[0].validator.status == "pass"
    assert snapshot.completed_at is not None


async def test_published_status_sequence_for_the_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch)
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_SQL_RESPONSE)
    snapshot = await _new_run()
    bus = get_event_bus(snapshot.run_id)

    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=bus,
        snapshot=snapshot,
        effective_question=snapshot.question,
        params=_DEFAULT_PARAMS,
    )

    statuses = [s.status async for s in bus.subscribe()]
    assert statuses == [
        "RECEIVED",
        "RETRIEVING",
        "GENERATING_SQL",
        "VALIDATING",
        "GENERATING_INSIGHT",
        "READY",
    ]


async def test_low_retrieval_score_pauses_for_clarification_without_calling_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, context=_LOW_SCORE_CONTEXT)
    provider = FakeLLMProvider()
    snapshot = await _new_run()

    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=get_event_bus(snapshot.run_id),
        snapshot=snapshot,
        effective_question=snapshot.question,
        params=_DEFAULT_PARAMS,
    )

    assert snapshot.status == "NEEDS_CLARIFICATION"
    assert snapshot.clarification_question is not None
    assert len(provider.calls) == 0


async def test_empty_retrieval_pauses_for_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, context=[])
    provider = FakeLLMProvider()
    snapshot = await _new_run()

    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=get_event_bus(snapshot.run_id),
        snapshot=snapshot,
        effective_question=snapshot.question,
        params=_DEFAULT_PARAMS,
    )

    assert snapshot.status == "NEEDS_CLARIFICATION"


async def test_low_nl2sql_confidence_pauses_for_clarification_without_validating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_store, validator, _insight = _install(monkeypatch, validator=_ScriptedValidator([]))
    provider = FakeLLMProvider()
    provider.register("hold time", _LOW_CONFIDENCE_RESPONSE)
    snapshot = await _new_run()

    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=get_event_bus(snapshot.run_id),
        snapshot=snapshot,
        effective_question=snapshot.question,
        params=_DEFAULT_PARAMS,
    )

    assert snapshot.status == "NEEDS_CLARIFICATION"
    assert snapshot.clarification_options == ["Q2 could mean fiscal or calendar quarter"]
    assert len(validator.calls) == 0


async def test_repairable_failure_then_pass_records_both_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch, validator=_ScriptedValidator([_repairable_fail("bad table"), _pass_output()])
    )
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_SQL_RESPONSE, _VALID_SQL_RESPONSE)
    snapshot = await _new_run()

    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=get_event_bus(snapshot.run_id),
        snapshot=snapshot,
        effective_question=snapshot.question,
        params=_DEFAULT_PARAMS,
    )

    assert snapshot.status == "READY"
    assert len(snapshot.attempts) == 2
    assert snapshot.attempts[0].validator.status == "fail"
    assert snapshot.attempts[1].validator.status == "pass"
    # The regenerated attempt must carry the validator's feedback forward.
    _, second_prompt = provider.calls[1]
    assert "VALIDATOR_FEEDBACK" in second_prompt
    assert "bad table" in second_prompt


async def test_exhausting_repairs_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        validator=_ScriptedValidator(
            [_repairable_fail("x"), _repairable_fail("y"), _repairable_fail("z")]
        ),
    )
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_SQL_RESPONSE, _VALID_SQL_RESPONSE, _VALID_SQL_RESPONSE)
    snapshot = await _new_run()

    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=get_event_bus(snapshot.run_id),
        snapshot=snapshot,
        effective_question=snapshot.question,
        params=_DEFAULT_PARAMS,
    )

    assert snapshot.status == "FAILED"
    assert len(snapshot.attempts) == 3
    assert snapshot.error == "z"


async def test_non_repairable_failure_fails_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, validator=_ScriptedValidator([_terminal_fail()]))
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_SQL_RESPONSE)
    snapshot = await _new_run()

    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=get_event_bus(snapshot.run_id),
        snapshot=snapshot,
        effective_question=snapshot.question,
        params=_DEFAULT_PARAMS,
    )

    assert snapshot.status == "FAILED"
    assert len(snapshot.attempts) == 1


async def test_nl2sql_generation_failure_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, validator=_ScriptedValidator([]))
    provider = FakeLLMProvider()  # no rules registered -> always "{}" -> unparseable
    snapshot = await _new_run()

    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=get_event_bus(snapshot.run_id),
        snapshot=snapshot,
        effective_question=snapshot.question,
        params=_DEFAULT_PARAMS,
    )

    assert snapshot.status == "FAILED"
    assert "NL2SQL" in (snapshot.error or "")


async def test_insight_failure_still_reaches_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, insight=_StubInsight(error=InsightGenerationError("model outage")))
    provider = FakeLLMProvider()
    provider.register("hold time", _VALID_SQL_RESPONSE)
    snapshot = await _new_run()

    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=get_event_bus(snapshot.run_id),
        snapshot=snapshot,
        effective_question=snapshot.question,
        params=_DEFAULT_PARAMS,
    )

    assert snapshot.status == "READY"
    assert snapshot.insight is None
    assert snapshot.insight_error == "model outage"


async def test_record_clarification_resumes_a_paused_run(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_store, _validator, _insight = _install(monkeypatch, context=_LOW_SCORE_CONTEXT)
    provider = FakeLLMProvider()
    snapshot = await _new_run()
    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=get_event_bus(snapshot.run_id),
        snapshot=snapshot,
        effective_question=snapshot.question,
        params=_DEFAULT_PARAMS,
    )
    assert snapshot.status == "NEEDS_CLARIFICATION"

    # Re-point search_catalog/validate_and_execute for the resumed attempt
    # (this time retrieval succeeds) while keeping the same fake store, so
    # the run persisted above is what gets resumed.
    _install(monkeypatch, context=_CONTEXT, fake_store=fake_store)
    provider.register("hold time", _VALID_SQL_RESPONSE)

    resumed, effective_question = await record_clarification(
        session=_UNUSED_SESSION, run_id=snapshot.run_id, answer="I mean the Buyer department"
    )
    status_after_resume = resumed.status  # read once: execute_run below mutates resumed in place
    assert status_after_resume == "RECEIVED"
    assert "Buyer department" in effective_question

    await execute_run(
        session=_UNUSED_SESSION,
        engine=_UNUSED_ENGINE,
        llm_provider=provider,
        embedding_provider=_UNUSED_EMBEDDING,
        bus=get_event_bus(snapshot.run_id),
        snapshot=resumed,
        effective_question=effective_question,
        params=_DEFAULT_PARAMS,
    )

    assert resumed.status == "READY"
    stored = await fake_store.get_run(_UNUSED_SESSION, snapshot.run_id)
    assert stored is not None and stored.status == "READY"


async def test_record_clarification_rejects_a_run_not_awaiting_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_store, _v, _i = _install(monkeypatch)
    snapshot = await _new_run()  # freshly created -> status RECEIVED, not NEEDS_CLARIFICATION

    with pytest.raises(NotAwaitingClarificationError):
        await record_clarification(session=_UNUSED_SESSION, run_id=snapshot.run_id, answer="x")


async def test_record_clarification_raises_lookup_error_for_unknown_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch)

    with pytest.raises(LookupError):
        await record_clarification(session=_UNUSED_SESSION, run_id=uuid.uuid4(), answer="x")


async def test_cancel_run_marks_a_non_terminal_run_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_store, _v, _i = _install(monkeypatch)
    snapshot = await _new_run()

    cancelled = await cancel_run(_UNUSED_SESSION, snapshot.run_id)

    assert cancelled is not None
    assert cancelled.status == "CANCELLED"
    assert cancelled.completed_at is not None


async def test_cancel_run_is_a_no_op_once_already_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_store, _v, _i = _install(monkeypatch)
    snapshot = await _new_run()
    await fake_store.save_run(_UNUSED_SESSION, snapshot.model_copy(update={"status": "READY"}))

    result = await cancel_run(_UNUSED_SESSION, snapshot.run_id)

    assert result is not None
    assert result.status == "READY"  # not overwritten to CANCELLED


async def test_cancel_run_returns_none_for_an_unknown_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)

    assert await cancel_run(_UNUSED_SESSION, uuid.uuid4()) is None
