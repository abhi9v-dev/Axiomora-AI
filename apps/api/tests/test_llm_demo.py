from __future__ import annotations

from app.db.seed import ANOMALY_DEPARTMENT
from app.insight.agent import generate_insight
from app.insight.verification import verify_claims
from app.llm.demo import DEMO_QUESTION_MATCH, build_demo_llm_provider
from app.nl2sql.agent import generate_sql
from app.validator.policy import validate_sql_policy
from app.validator.schema import QueryResult

_DEMO_QUESTION = "Why did median task hold time spike for the Buyer department in Q2?"


def test_demo_question_match_is_the_seeded_anomaly_department() -> None:
    assert DEMO_QUESTION_MATCH == ANOMALY_DEPARTMENT
    assert ANOMALY_DEPARTMENT in _DEMO_QUESTION


async def test_demo_provider_answers_the_canonical_question_with_valid_sql() -> None:
    provider = build_demo_llm_provider()

    nl2sql_output = await generate_sql(
        provider, question=_DEMO_QUESTION, dialect="postgres", retrieved_context=[]
    )

    assert nl2sql_output.confidence >= 0.4  # above NL2SQL_MIN_CONFIDENCE's default
    policy = validate_sql_policy(nl2sql_output.sql)
    assert policy.ok, policy.violations
    assert policy.placeholders <= set(nl2sql_output.parameters.keys())


async def test_demo_provider_then_answers_insight_with_a_grounded_claim() -> None:
    provider = build_demo_llm_provider()
    await generate_sql(provider, question=_DEMO_QUESTION, dialect="postgres", retrieved_context=[])

    result = QueryResult(
        columns=["quarter", "median_hold_hrs"],
        rows=[["2026-Q1", 9.5], ["2026-Q2", 27.4]],
        row_count=2,
        truncated=False,
    )
    insight_output = await generate_insight(provider, question=_DEMO_QUESTION, result=result)

    assert insight_output.claims
    assert verify_claims(result, insight_output).ok


async def test_an_unscripted_question_falls_back_to_the_default_empty_response() -> None:
    provider = build_demo_llm_provider()

    raw = await provider.complete(system="s", user="Some entirely different question")

    assert raw == "{}"
