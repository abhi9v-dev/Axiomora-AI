"""Typed, validated application configuration.

Field names intentionally mirror the environment variable names from the
configuration contract in docs/03_ARCHITECTURE.md so the mapping between
`.env` and settings is unambiguous. All values are read from the process
environment (or a local `.env` file) -- nothing here is a real secret.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "test", "staging", "production"] = "development"

    # Application database: runs, audit events, catalog/pgvector (Phase 2+).
    DATABASE_URL: str

    # Read-only analytical warehouse (Phase 1+). Required now so misconfiguration
    # fails at startup rather than surfacing deep inside a later phase.
    WAREHOUSE_URL: str

    # LLM provider selection (Phase 3+). Defaults to the deterministic fake
    # provider so the app runs with zero external calls out of the box.
    LLM_PROVIDER: Literal["fake", "anthropic"] = "fake"
    ANTHROPIC_API_KEY: str | None = None
    LLM_MODEL: str = "claude-sonnet-5"

    # Embedding provider selection (Phase 2+).
    EMBEDDING_PROVIDER: str = "fake"

    # SQL validator / execution policy (Phase 4+).
    MAX_SQL_REPAIRS: int = 2
    QUERY_TIMEOUT_MS: int = 10_000
    QUERY_ROW_LIMIT: int = 5_000

    # Power BI adapter (Phase 8+). Must stay disabled by default.
    POWER_BI_ENABLED: bool = False

    # API service.
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000"

    @model_validator(mode="after")
    def _validate_llm_provider_requirements(self) -> Settings:
        if self.LLM_PROVIDER == "anthropic" and not self.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic. "
                "Use LLM_PROVIDER=fake for local development without a key."
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton, loaded and validated once."""
    return Settings()  # values are loaded from the environment / .env at runtime
