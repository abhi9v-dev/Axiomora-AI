"""marketplace operations schema, analytics views, read-only role

Revision ID: 0001
Revises:
Create Date: 2026-08-28

Creates the marketplace/organisation warehouse tables, the three
analytics.* rollup views (ported from the real view definitions supplied
for this project -- see docs/adr/0003-marketplace-operations-demo-domain.md),
and a read-only `bi_readonly` role scoped to SELECT on these three schemas
only. `bi_readonly`'s password is a well-known local/demo placeholder
(matches WAREHOUSE_URL in .env.example) -- rotate it for any non-local use.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMAS = ("organisation", "marketplace", "analytics")

_READONLY_ROLE = "bi_readonly"
_READONLY_PASSWORD = "changeme"  # local/demo placeholder, matches .env.example


def upgrade() -> None:
    for schema in _SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    op.create_table(
        "department",
        sa.Column("departmentid", sa.Integer(), primary_key=True),
        sa.Column("departmentname", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("createdby", sa.Text(), nullable=True),
        sa.Column("creationdate", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lastmodifiedby", sa.Text(), nullable=True),
        sa.Column("lastmodifieddate", sa.DateTime(timezone=True), nullable=True),
        schema="organisation",
    )

    op.create_table(
        "account",
        sa.Column("accountid", sa.Integer(), primary_key=True),
        sa.Column("forename", sa.Text(), nullable=False),
        sa.Column("surname", sa.Text(), nullable=False),
        schema="organisation",
    )

    op.create_table(
        "projectstage",
        sa.Column("projectstage", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        schema="marketplace",
    )

    op.create_table(
        "projectstatus",
        sa.Column("project_status", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        schema="marketplace",
    )

    op.create_table(
        "project_sub_status",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        schema="marketplace",
    )

    op.create_table(
        "projects",
        sa.Column("projectid", sa.Integer(), primary_key=True),
        sa.Column("projectname", sa.Text(), nullable=False),
        sa.Column(
            "stage",
            sa.Integer(),
            sa.ForeignKey("marketplace.projectstage.projectstage"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Integer(),
            sa.ForeignKey("marketplace.projectstatus.project_status"),
            nullable=False,
        ),
        sa.Column(
            "project_sub_status_id",
            sa.Integer(),
            sa.ForeignKey("marketplace.project_sub_status.id"),
            nullable=True,
        ),
        sa.Column("projectcategory", sa.Text(), nullable=True),
        sa.Column("creationdate", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submittedat", sa.DateTime(timezone=True), nullable=True),
        schema="marketplace",
    )
    op.create_index(
        "ix_projects_stage_status", "projects", ["stage", "status"], schema="marketplace"
    )

    op.create_table(
        "task",
        sa.Column("taskid", sa.Integer(), primary_key=True),
        sa.Column("taskname", sa.Text(), nullable=False),
        sa.Column("tasktype", sa.Text(), nullable=False),
        sa.Column("tasksubtype", sa.Text(), nullable=True),
        sa.Column("taskstatus", sa.Text(), nullable=False),
        sa.Column(
            "projectid",
            sa.Integer(),
            sa.ForeignKey("marketplace.projects.projectid"),
            nullable=False,
        ),
        sa.Column(
            "departmentid",
            sa.Integer(),
            sa.ForeignKey("organisation.department.departmentid"),
            nullable=True,
        ),
        sa.Column(
            "assigneeaccountid",
            sa.Integer(),
            sa.ForeignKey("organisation.account.accountid"),
            nullable=True,
        ),
        sa.Column(
            "completedbyaccountid",
            sa.Integer(),
            sa.ForeignKey("organisation.account.accountid"),
            nullable=True,
        ),
        sa.Column("createddatetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimedon", sa.DateTime(timezone=True), nullable=True),
        sa.Column("startedon", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completedon", sa.DateTime(timezone=True), nullable=True),
        schema="marketplace",
    )
    op.create_index("ix_task_projectid", "task", ["projectid"], schema="marketplace")
    op.create_index("ix_task_departmentid", "task", ["departmentid"], schema="marketplace")
    op.create_index(
        "ix_task_type_subtype", "task", ["tasktype", "tasksubtype"], schema="marketplace"
    )

    # --- analytics views (ported from the supplied View_DB(1).sql) ---

    op.execute("""
        CREATE OR REPLACE VIEW analytics.v_snapshot AS
        SELECT max(GREATEST(
                   t.createddatetime,
                   COALESCE(t.claimedon,   '-infinity'::timestamptz),
                   COALESCE(t.startedon,   '-infinity'::timestamptz),
                   COALESCE(t.completedon, '-infinity'::timestamptz)
               )) AS as_of
        FROM marketplace.task t
        """)

    op.execute("""
        CREATE OR REPLACE VIEW analytics.v_task_lifecycle AS
        WITH snap AS (SELECT as_of FROM analytics.v_snapshot)
        SELECT
            t.taskid,
            t.taskname,
            t.tasktype,
            t.tasksubtype,
            t.taskstatus,

            t.projectid,
            p.projectname,
            pstg.name                        AS project_stage,
            pst.name                         AS project_status,
            pss.name                         AS project_sub_status,

            t.departmentid,
            COALESCE(d.departmentname, 'Unassigned')            AS department_name,
            t.assigneeaccountid,
            CASE WHEN t.assigneeaccountid IS NULL THEN 'Unclaimed'
                 ELSE COALESCE(a.forename || ' ' || a.surname,
                               'Account ' || t.assigneeaccountid)
            END                                                 AS assignee_name,
            t.completedbyaccountid,

            t.createddatetime,
            t.claimedon,
            t.startedon,
            t.completedon,

            EXTRACT(ISODOW FROM t.createddatetime)::int         AS created_dow,
            to_char(t.createddatetime, 'Dy')                    AS created_dow_name,
            EXTRACT(HOUR  FROM t.createddatetime)::int          AS created_hour,
            (EXTRACT(ISODOW FROM t.createddatetime) >= 6)       AS created_on_weekend,

            ROUND(EXTRACT(EPOCH FROM (t.claimedon - t.createddatetime))/3600.0, 3)
                                                                AS claim_wait_hrs,
            ROUND(EXTRACT(EPOCH FROM (t.startedon - t.claimedon))/3600.0, 3)
                                                                AS start_delay_hrs,
            ROUND(EXTRACT(EPOCH FROM (t.completedon - t.startedon))/3600.0, 3)
                                                                AS working_time_hrs,
            ROUND(EXTRACT(EPOCH FROM (t.completedon - t.claimedon))/3600.0, 3)
                                                                AS assignee_hold_hrs,
            ROUND(EXTRACT(EPOCH FROM (t.completedon - t.createddatetime))/3600.0, 3)
                                                                AS total_duration_hrs,

            CASE WHEN t.completedon IS NULL
                 THEN ROUND(EXTRACT(EPOCH FROM (s.as_of - t.createddatetime))/3600.0, 3)
            END                                                 AS open_age_hrs,

            CASE WHEN t.claimedon IS NULL AND t.completedon IS NULL
                 THEN ROUND(EXTRACT(EPOCH FROM (s.as_of - t.createddatetime))/3600.0, 3)
            END                                                 AS unclaimed_age_hrs,

            CASE WHEN t.completedon IS NOT NULL THEN 'Completed'
                 WHEN t.startedon   IS NOT NULL THEN 'In Progress'
                 WHEN t.claimedon   IS NOT NULL THEN 'Claimed, not started'
                 ELSE 'Unclaimed'
            END                                                 AS lifecycle_state,

            CASE
              WHEN (t.claimedon   IS NOT NULL AND t.claimedon   < t.createddatetime)
                OR (t.startedon   IS NOT NULL AND t.claimedon IS NOT NULL
                    AND t.startedon   < t.claimedon)
                OR (t.completedon IS NOT NULL AND t.startedon IS NOT NULL
                    AND t.completedon < t.startedon)
                OR (t.completedon IS NOT NULL AND t.completedon < t.createddatetime)
                                                            THEN 'ANOMALY_ORDER'
              WHEN t.completedon IS NULL                    THEN 'OPEN'
              WHEN t.claimedon   IS NULL                    THEN 'COMPLETE_NO_CLAIM'
              WHEN t.startedon   IS NULL                    THEN 'COMPLETE_NO_START'
              ELSE                                               'COMPLETE_FULL'
            END                                                 AS quality_flag,

            (
              NOT (
                (t.claimedon   IS NOT NULL AND t.claimedon   < t.createddatetime)
                OR (t.startedon   IS NOT NULL AND t.claimedon IS NOT NULL
                    AND t.startedon   < t.claimedon)
                OR (t.completedon IS NOT NULL AND t.startedon IS NOT NULL
                    AND t.completedon < t.startedon)
                OR (t.completedon IS NOT NULL AND t.completedon < t.createddatetime)
              )
            )                                                   AS is_measurable,

            s.as_of                                             AS snapshot_as_of

        FROM marketplace.task t
        CROSS JOIN snap s
        LEFT JOIN marketplace.projects           p    ON p.projectid       = t.projectid
        LEFT JOIN marketplace.projectstage       pstg ON pstg.projectstage = p.stage
        LEFT JOIN marketplace.projectstatus      pst  ON pst.project_status = p.status
        LEFT JOIN marketplace.project_sub_status pss  ON pss.id            = p.project_sub_status_id
        LEFT JOIN organisation.department        d    ON d.departmentid    = t.departmentid
        LEFT JOIN organisation.account           a    ON a.accountid       = t.assigneeaccountid
        WHERE t.projectid IS NOT NULL
        """)

    op.execute("""
        CREATE OR REPLACE VIEW analytics.v_project_status AS
        WITH snap AS (SELECT as_of FROM analytics.v_snapshot),
        task_rollup AS (
            SELECT projectid,
                   count(*)                                          AS task_count,
                   count(*) FILTER (WHERE completedon IS NULL)        AS open_task_count,
                   count(*) FILTER (WHERE claimedon IS NULL
                                      AND completedon IS NULL)        AS unclaimed_task_count,
                   max(GREATEST(createddatetime,
                                COALESCE(claimedon,  '-infinity'::timestamptz),
                                COALESCE(startedon,  '-infinity'::timestamptz),
                                COALESCE(completedon,'-infinity'::timestamptz)))
                                                                      AS last_task_event
            FROM marketplace.task
            WHERE projectid IS NOT NULL
            GROUP BY projectid
        )
        SELECT
            p.projectid,
            p.projectname,
            COALESCE(pstg.name, 'Unknown stage')   AS project_stage,
            COALESCE(pst.name,  'Unknown status')  AS project_status,
            COALESCE(pss.name,  'Not set')         AS project_sub_status,
            p.projectcategory,
            p.creationdate                         AS project_created,
            p.submittedat,

            ROUND(EXTRACT(EPOCH FROM (s.as_of - p.creationdate))/86400.0, 2) AS project_age_days,

            CASE
              WHEN EXTRACT(EPOCH FROM (s.as_of - p.creationdate))/86400.0 <  3 THEN '0-2 days'
              WHEN EXTRACT(EPOCH FROM (s.as_of - p.creationdate))/86400.0 <  8 THEN '3-7 days'
              WHEN EXTRACT(EPOCH FROM (s.as_of - p.creationdate))/86400.0 < 15 THEN '8-14 days'
              ELSE '15+ days'
            END                                    AS age_bucket,

            CASE
              WHEN EXTRACT(EPOCH FROM (s.as_of - p.creationdate))/86400.0 <  3 THEN 1
              WHEN EXTRACT(EPOCH FROM (s.as_of - p.creationdate))/86400.0 <  8 THEN 2
              WHEN EXTRACT(EPOCH FROM (s.as_of - p.creationdate))/86400.0 < 15 THEN 3
              ELSE 4
            END                                    AS age_bucket_sort,

            COALESCE(tr.task_count, 0)             AS task_count,
            COALESCE(tr.open_task_count, 0)        AS open_task_count,
            COALESCE(tr.unclaimed_task_count, 0)   AS unclaimed_task_count,
            tr.last_task_event,

            ROUND(EXTRACT(EPOCH FROM (s.as_of - tr.last_task_event))/86400.0, 2)
                                                   AS days_since_last_activity,

            CASE
              WHEN pst.name IN ('Completed','Archived') THEN FALSE
              WHEN tr.last_task_event IS NULL           THEN NULL
              WHEN EXTRACT(EPOCH FROM (s.as_of - tr.last_task_event))/86400.0 >= 14
                                                        THEN TRUE
              ELSE FALSE
            END                                    AS is_stuck,

            (pst.name NOT IN ('Completed','Archived')) AS is_active,
            s.as_of                                AS snapshot_as_of

        FROM marketplace.projects p
        CROSS JOIN snap s
        LEFT JOIN marketplace.projectstage       pstg ON pstg.projectstage  = p.stage
        LEFT JOIN marketplace.projectstatus      pst  ON pst.project_status = p.status
        LEFT JOIN marketplace.project_sub_status pss  ON pss.id = p.project_sub_status_id
        LEFT JOIN task_rollup                    tr   ON tr.projectid = p.projectid
        """)

    # --- read-only warehouse role, scoped to SELECT on these 3 schemas ---

    op.execute(f"""
        DO $$
        BEGIN
           IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{_READONLY_ROLE}') THEN
              CREATE ROLE {_READONLY_ROLE} WITH LOGIN PASSWORD '{_READONLY_PASSWORD}';
           END IF;
        END
        $$;
        """)
    op.execute(f"GRANT USAGE ON SCHEMA {', '.join(_SCHEMAS)} TO {_READONLY_ROLE}")
    op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {', '.join(_SCHEMAS)} TO {_READONLY_ROLE}")
    for schema in _SCHEMAS:
        op.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} "
            f"GRANT SELECT ON TABLES TO {_READONLY_ROLE}"
        )


def downgrade() -> None:
    schemas = ", ".join(_SCHEMAS)
    op.execute(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {schemas} FROM {_READONLY_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA {schemas} FROM {_READONLY_ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {_READONLY_ROLE}")

    op.execute("DROP VIEW IF EXISTS analytics.v_project_status")
    op.execute("DROP VIEW IF EXISTS analytics.v_task_lifecycle")
    op.execute("DROP VIEW IF EXISTS analytics.v_snapshot")

    op.drop_table("task", schema="marketplace")
    op.drop_table("projects", schema="marketplace")
    op.drop_table("project_sub_status", schema="marketplace")
    op.drop_table("projectstatus", schema="marketplace")
    op.drop_table("projectstage", schema="marketplace")
    op.drop_table("account", schema="organisation")
    op.drop_table("department", schema="organisation")

    for schema in _SCHEMAS:
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
