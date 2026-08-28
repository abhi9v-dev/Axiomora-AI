"""SQLAlchemy 2 ORM models for the marketplace-operations warehouse.

Schema mirrors the real marketplace/organisation platform schema provided
for this project (see docs/adr/0003-marketplace-operations-demo-domain.md);
every row inserted through app.db.seed is fabricated. The three
`analytics.*` views (v_snapshot, v_task_lifecycle, v_project_status) are
pure read-only SQL and are created directly in the Alembic migration rather
than mapped here -- they have no independent existence to seed or migrate.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_TZ = DateTime(timezone=True)


class ProjectStage(Base):
    __tablename__ = "projectstage"
    __table_args__ = {"schema": "marketplace"}

    projectstage: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)


class ProjectStatus(Base):
    __tablename__ = "projectstatus"
    __table_args__ = {"schema": "marketplace"}

    project_status: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)


class ProjectSubStatus(Base):
    __tablename__ = "project_sub_status"
    __table_args__ = {"schema": "marketplace"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {"schema": "marketplace"}

    projectid: Mapped[int] = mapped_column(primary_key=True)
    projectname: Mapped[str] = mapped_column(Text)
    stage: Mapped[int] = mapped_column(ForeignKey("marketplace.projectstage.projectstage"))
    status: Mapped[int] = mapped_column(ForeignKey("marketplace.projectstatus.project_status"))
    project_sub_status_id: Mapped[int | None] = mapped_column(
        ForeignKey("marketplace.project_sub_status.id")
    )
    projectcategory: Mapped[str | None] = mapped_column(Text)
    creationdate: Mapped[dt.datetime] = mapped_column(_TZ)
    submittedat: Mapped[dt.datetime | None] = mapped_column(_TZ)


class Task(Base):
    __tablename__ = "task"
    __table_args__ = {"schema": "marketplace"}

    taskid: Mapped[int] = mapped_column(primary_key=True)
    taskname: Mapped[str] = mapped_column(Text)
    tasktype: Mapped[str] = mapped_column(Text)
    tasksubtype: Mapped[str | None] = mapped_column(Text)
    taskstatus: Mapped[str] = mapped_column(Text)
    projectid: Mapped[int] = mapped_column(ForeignKey("marketplace.projects.projectid"))
    departmentid: Mapped[int | None] = mapped_column(
        ForeignKey("organisation.department.departmentid")
    )
    assigneeaccountid: Mapped[int | None] = mapped_column(
        ForeignKey("organisation.account.accountid")
    )
    completedbyaccountid: Mapped[int | None] = mapped_column(
        ForeignKey("organisation.account.accountid")
    )
    createddatetime: Mapped[dt.datetime] = mapped_column(_TZ)
    claimedon: Mapped[dt.datetime | None] = mapped_column(_TZ)
    startedon: Mapped[dt.datetime | None] = mapped_column(_TZ)
    completedon: Mapped[dt.datetime | None] = mapped_column(_TZ)


class Department(Base):
    __tablename__ = "department"
    __table_args__ = {"schema": "organisation"}

    departmentid: Mapped[int] = mapped_column(primary_key=True)
    departmentname: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    createdby: Mapped[str | None] = mapped_column(Text)
    creationdate: Mapped[dt.datetime] = mapped_column(_TZ)
    lastmodifiedby: Mapped[str | None] = mapped_column(Text)
    lastmodifieddate: Mapped[dt.datetime | None] = mapped_column(_TZ)


class Account(Base):
    __tablename__ = "account"
    __table_args__ = {"schema": "organisation"}

    accountid: Mapped[int] = mapped_column(primary_key=True)
    forename: Mapped[str] = mapped_column(Text)
    surname: Mapped[str] = mapped_column(Text)
