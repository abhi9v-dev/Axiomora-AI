"""The warehouse SQL policy allowlist (docs/07_SECURITY_GOVERNANCE.md).

Allowed tables/views are derived from the real ORM metadata (app.db.models)
rather than hand-maintained as a parallel list, so this can never silently
drift from the actual schema migration 0001 creates. The three analytics
views aren't ORM-mapped (they're raw SQL in the migration -- see
app.db.catalog_models's docstring on why catalog.* is deliberately
excluded: it's application infrastructure, not warehouse data) so they're
listed explicitly. `catalog.*` is never included here -- NL2SQL-generated
SQL only ever queries the warehouse, never the catalog store.
"""

from __future__ import annotations

import app.db.models  # noqa: F401  (registers marketplace/organisation tables on Base.metadata)
from app.db.base import Base

_WAREHOUSE_SCHEMAS = ("marketplace", "organisation")

_ANALYTICS_VIEWS = (
    "analytics.v_snapshot",
    "analytics.v_task_lifecycle",
    "analytics.v_project_status",
)


def _split_object_name(full_name: str) -> tuple[str, str]:
    schema, _, table = full_name.partition(".")
    return schema, table


ALLOWED_OBJECTS: frozenset[tuple[str, str]] = frozenset(
    _split_object_name(full_name)
    for full_name in (
        *(name for name in Base.metadata.tables if name.split(".", 1)[0] in _WAREHOUSE_SCHEMAS),
        *_ANALYTICS_VIEWS,
    )
)

# Functions sqlglot doesn't recognize as a standard SQL construct parse as
# exp.Anonymous (see app.validator.policy) -- this is exactly where every
# dangerous Postgres-specific function (pg_read_file, dblink, pg_sleep,
# lo_import, current_setting/set_config, pg_terminate_backend, ...) lands,
# since sqlglot has no dedicated expression class for them. Default-deny
# that whole bucket; only these vetted, benign names are allowed through.
ALLOWED_ANONYMOUS_FUNCTIONS: frozenset[str] = frozenset({"age"})
