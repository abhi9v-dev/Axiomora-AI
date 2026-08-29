from __future__ import annotations

from app.insight.schema import Claim, InsightOutput
from app.insight.verification import extract_numbers, verify_claims
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


def test_extract_numbers_finds_decimals_and_integers() -> None:
    assert extract_numbers("Median hold time moved from 9.5 hours to 27.4 hours") == [9.5, 27.4]


def test_extract_numbers_ignores_digits_embedded_in_words() -> None:
    # "Q2" should not be read as the number 2.
    assert extract_numbers("Hold time spiked in Q2 for the Buyer department") == []


def test_extract_numbers_handles_thousands_separators_and_percent() -> None:
    assert extract_numbers("Volume rose 18% to 1,234 tasks") == [18.0, 1234.0]


def test_grounded_claim_passes_verification() -> None:
    output = InsightOutput(
        headline="Buyer department median hold time increased 18 hours in Q2",
        narrative="The increase followed a spike in Supplier Compliance Review tasks.",
        claims=[
            Claim(
                text="Median hold time moved from 9.5 hours to 27.4 hours",
                evidence=["result:r1:c3", "result:r2:c3"],
            )
        ],
    )

    verification = verify_claims(_RESULT, output)

    assert verification.ok
    assert verification.violations == []


def test_claim_with_number_but_no_evidence_is_a_violation() -> None:
    output = InsightOutput(
        headline="h",
        narrative="n",
        claims=[Claim(text="Median hold time is 27.4 hours", evidence=[])],
    )

    verification = verify_claims(_RESULT, output)

    assert not verification.ok
    assert "cites no evidence" in verification.violations[0]


def test_claim_number_not_matching_cited_evidence_is_a_violation() -> None:
    output = InsightOutput(
        headline="h",
        narrative="n",
        claims=[Claim(text="Median hold time reached 99.9 hours", evidence=["result:r2:c3"])],
    )

    verification = verify_claims(_RESULT, output)

    assert not verification.ok
    assert "99.9" in verification.violations[0]


def test_dangling_evidence_reference_is_a_violation() -> None:
    output = InsightOutput(
        headline="h",
        narrative="n",
        claims=[Claim(text="Median hold time reached 27.4 hours", evidence=["result:r9:c9"])],
    )

    verification = verify_claims(_RESULT, output)

    assert not verification.ok
    assert any("out of range" in v for v in verification.violations)


def test_non_numeric_claim_needs_no_evidence() -> None:
    output = InsightOutput(
        headline="h",
        narrative="n",
        claims=[Claim(text="Buyer department drove the change", evidence=[])],
    )

    verification = verify_claims(_RESULT, output)

    assert verification.ok


def test_empty_claims_list_passes_trivially() -> None:
    output = InsightOutput(headline="No data found.", narrative="No rows returned.", claims=[])

    verification = verify_claims(_RESULT, output)

    assert verification.ok
