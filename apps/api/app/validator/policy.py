"""Static SQL policy validation (FR-005, docs/07_SECURITY_GOVERNANCE.md).

Parses model-generated SQL with SQLGlot and enforces, entirely offline (no
database access): exactly one statement, that statement must be a SELECT
with no side-effecting clauses (e.g. `SELECT ... INTO`), every referenced
table/view must be fully-qualified and in ALLOWED_OBJECTS, and every
function SQLGlot doesn't recognize as standard SQL vocabulary must be in
ALLOWED_ANONYMOUS_FUNCTIONS. This is the one gate model-generated SQL must
pass before app.validator.executor ever sees it: "Never execute
model-generated SQL without AST parsing and policy validation."

SQL comments cannot smuggle a second statement or hide DDL/DML here --
SQLGlot parses structure, not text, so a comment is simply not part of the
statement tree regardless of what it contains.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.validator.allowlist import ALLOWED_ANONYMOUS_FUNCTIONS, ALLOWED_OBJECTS

DIALECT = "postgres"


@dataclass
class PolicyResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    referenced_objects: list[str] = field(default_factory=list)
    placeholders: set[str] = field(default_factory=set)
    normalized_sql: str | None = None


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.this).lower()
    return node.sql_name().lower()


def validate_sql_policy(sql: str) -> PolicyResult:
    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
    except ParseError as exc:
        return PolicyResult(ok=False, violations=[f"SQL failed to parse: {exc}"])

    if len(statements) == 0:
        return PolicyResult(ok=False, violations=["No SQL statement was found."])
    if len(statements) > 1:
        return PolicyResult(
            ok=False,
            violations=[f"Exactly one SQL statement is allowed; found {len(statements)}."],
        )

    stmt = statements[0]

    if not isinstance(stmt, exp.Select):
        return PolicyResult(
            ok=False,
            violations=[
                "Only a single read-only SELECT statement is allowed; "
                f"found {type(stmt).__name__}."
            ],
        )

    violations: list[str] = []

    if stmt.args.get("into") is not None:
        violations.append("SELECT ... INTO is not allowed (it creates a table as a side effect).")

    referenced_objects: list[str] = []
    for table in stmt.find_all(exp.Table):
        if not table.db:
            violations.append(
                f"Table '{table.name}' must be schema-qualified (e.g. marketplace.{table.name})."
            )
            continue
        full_name = f"{table.db}.{table.name}"
        if (table.db, table.name) not in ALLOWED_OBJECTS:
            violations.append(f"'{full_name}' is not an approved table or view.")
        referenced_objects.append(full_name)

    for func in stmt.find_all(exp.Func):
        if isinstance(func, exp.Anonymous):
            name = _function_name(func)
            if name not in ALLOWED_ANONYMOUS_FUNCTIONS:
                violations.append(f"Function '{name}(...)' is not an approved function.")

    if violations:
        return PolicyResult(
            ok=False, violations=violations, referenced_objects=sorted(set(referenced_objects))
        )

    placeholders = {p.this for p in stmt.find_all(exp.Placeholder) if isinstance(p.this, str)}
    return PolicyResult(
        ok=True,
        referenced_objects=sorted(set(referenced_objects)),
        placeholders=placeholders,
        normalized_sql=stmt.sql(dialect=DIALECT),
    )
