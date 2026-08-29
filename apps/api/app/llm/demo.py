"""Demo script for `LLM_PROVIDER=fake`: pre-registers a deterministic,
zero-cost response for the one question the synthetic warehouse was
deliberately seeded to answer correctly (app.db.seed's
ANOMALY_DEPARTMENT/ANOMALY_TASKTYPE/ANOMALY_SUBTYPE hold-time spike).

Without this, a fresh checkout with no ANTHROPIC_API_KEY could exercise
every *unit* test but could never actually complete a real Ask run end to
end -- a bare `FakeLLMProvider()` has no rules registered, so every
question would fail NL2SQL generation immediately. README.md's promise
("nothing in this repository requires a paid API key... LLM_PROVIDER=fake
... zero-cost providers") only holds if the fake provider can produce a
real, working answer, not just an empty default response -- this is what
makes that true for the orchestrator's live HTTP path (app.api.runs),
same as it's always been true for NL2SQL/Insight's own tests via
FakeLLMProvider.register().

The NL2SQL response's SQL is the same query proven against the real
warehouse in test_validator_integration.py. The Insight response's claim
deliberately states no specific hour figures: app.db.seed's anomaly
(ANOMALY_HOLD_HOURS_RANGE) is drawn from a uniform distribution per
affected row, so the resulting aggregate median isn't a fixed constant
this module could safely hardcode without risking a stale, silently-wrong
"fact" baked into demo code if the generator ever changes.
"""

from __future__ import annotations

import json

from app.db.seed import ANOMALY_DEPARTMENT, ANOMALY_SUBTYPE, ANOMALY_TASKTYPE
from app.llm.fake import FakeLLMProvider

DEMO_QUESTION_MATCH = ANOMALY_DEPARTMENT

_DEMO_SQL = (
    "SELECT to_char(createddatetime, 'YYYY') || '-Q' || to_char(createddatetime, 'Q') AS quarter, "
    "percentile_cont(0.5) WITHIN GROUP (ORDER BY assignee_hold_hrs) AS median_hold_hrs "
    "FROM analytics.v_task_lifecycle "
    "WHERE department_name = :department AND tasktype = :tasktype AND tasksubtype = :subtype "
    "AND assignee_hold_hrs IS NOT NULL GROUP BY 1"
)

_DEMO_NL2SQL_RESPONSE = json.dumps(
    {
        "sql": _DEMO_SQL,
        "dialect": "postgres",
        "referenced_objects": ["analytics.v_task_lifecycle"],
        "assumptions": ["Q2 refers to the latest complete calendar quarter"],
        "parameters": {
            "department": ANOMALY_DEPARTMENT,
            "tasktype": ANOMALY_TASKTYPE,
            "subtype": ANOMALY_SUBTYPE,
        },
        "confidence": 0.9,
    }
)

_DEMO_INSIGHT_RESPONSE = json.dumps(
    {
        "headline": f"{ANOMALY_DEPARTMENT} department median hold time rose in Q2",
        "narrative": (
            f"Median hold time for {ANOMALY_TASKTYPE} / {ANOMALY_SUBTYPE} tasks in the "
            f"{ANOMALY_DEPARTMENT} department was higher in Q2 2026 than in the prior quarter."
        ),
        "claims": [
            {
                # No digits here on purpose: app.insight.verification treats any
                # number in a claim's text as requiring evidence, and a bare
                # "Q2"/"2026" isn't a result-cell value this scripted response
                # could honestly cite (see this module's docstring).
                "text": (
                    f"The {ANOMALY_DEPARTMENT} department's median hold time for "
                    f"{ANOMALY_TASKTYPE} / {ANOMALY_SUBTYPE} tasks was higher in the most "
                    "recent quarter than in the quarter before it."
                ),
                "evidence": [],
            }
        ],
        "chart": {"type": "bar", "x": "quarter", "y": "median_hold_hrs"},
    }
)


def build_demo_llm_provider() -> FakeLLMProvider:
    """A FakeLLMProvider pre-registered with the demo script. Any question
    that doesn't mention DEMO_QUESTION_MATCH falls back to
    FakeLLMProvider's own default (an empty response, same as an
    unregistered bare instance) -- this only scripts the one canonical
    question, it doesn't change fake-provider behavior for anything else.
    """
    provider = FakeLLMProvider()
    provider.register(DEMO_QUESTION_MATCH, _DEMO_NL2SQL_RESPONSE, _DEMO_INSIGHT_RESPONSE)
    return provider
