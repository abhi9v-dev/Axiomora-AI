"""Compact result serialization and evidence cell IDs
(docs/06_DATA_MODEL_API_CONTRACTS.md's Insight output example: "evidence":
["result:r2:c4", ...]).

A cell ID identifies exactly one value in a validated QueryResult by its
1-indexed row and column: `result:r{row}:c{col}`. `serialize_result` turns
the result into a compact, cell-ID-annotated block for the Insight Agent's
prompt (app.insight.prompts); `resolve_cell` turns a cell ID back into the
value it names, so app.insight.verification can check that a claim's
numbers actually match the cells it cites -- the model never gets to just
assert a citation is valid.
"""

from __future__ import annotations

import re

from app.validator.schema import QueryResult

_CELL_ID_PATTERN = re.compile(r"^result:r(\d+):c(\d+)$")


class CellReferenceError(Exception):
    """Raised by resolve_cell when a cell ID is malformed or points outside
    the result's actual row/column bounds -- i.e. a hallucinated citation."""


def cell_id(row: int, col: int) -> str:
    """row and col are 1-indexed, matching resolve_cell and the docs/06 example."""
    return f"result:r{row}:c{col}"


def resolve_cell(result: QueryResult, ref: str) -> object:
    match = _CELL_ID_PATTERN.match(ref)
    if match is None:
        raise CellReferenceError(f"'{ref}' is not a well-formed result cell reference.")

    row, col = int(match.group(1)), int(match.group(2))
    if not (1 <= row <= len(result.rows)) or not (1 <= col <= len(result.columns)):
        raise CellReferenceError(
            f"'{ref}' is out of range for a result with {len(result.rows)} row(s) and "
            f"{len(result.columns)} column(s)."
        )
    return result.rows[row - 1][col - 1]


def serialize_result(result: QueryResult) -> str:
    """A compact, cell-ID-annotated rendering of a QueryResult, suitable for
    an LLM prompt. Each cell is tagged with the exact ID a claim must cite
    to reference it, so the model can copy IDs directly rather than
    constructing them itself."""
    if result.row_count == 0:
        return "(no rows)"

    header = "columns: " + ", ".join(
        f"c{col}={name}" for col, name in enumerate(result.columns, start=1)
    )
    lines = [header]
    for row_idx, row in enumerate(result.rows, start=1):
        cells = " ".join(f"c{col}={value!r}" for col, value in enumerate(row, start=1))
        lines.append(f"r{row_idx}: {cells}")
    return "\n".join(lines)
