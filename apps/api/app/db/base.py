"""Shared SQLAlchemy declarative base.

Both the warehouse models (app.db.models) and the catalog models
(app.db.catalog_models) register on this same metadata, so Alembic's
autogenerate/target_metadata sees every table from one place.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
