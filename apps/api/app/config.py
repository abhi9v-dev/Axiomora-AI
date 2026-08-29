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

    # Orchestrator clarification thresholds (Phase 6+): below these, the
    # run pauses at NEEDS_CLARIFICATION instead of guessing
    # (docs/03_ARCHITECTURE.md: "retrieval below threshold: request
    # clarification; do not guess"). Not otherwise specified in the docs;
    # tuned for the fake providers' behavior, override per real provider.
    RETRIEVAL_MIN_SCORE: float = 0.2
    NL2SQL_MIN_CONFIDENCE: float = 0.4

    # Power BI adapter (Phase 8+). Must stay disabled by default -- when
    # False, app.action.policy never allows a power_bi_* action regardless
    # of POWER_BI_ADAPTER. "mock" (the default) needs no real tenant and is
    # what CI/local demos exercise; "rest" makes real, metered Power BI REST
    # calls and requires a Microsoft Entra app registration
    # (docs/09_DEPLOYMENT_OPERATIONS.md's "Power BI reality check").
    POWER_BI_ENABLED: bool = False
    POWER_BI_ADAPTER: Literal["mock", "rest"] = "mock"
    POWER_BI_WORKSPACE_ID: str = "demo-workspace"
    POWER_BI_DATASET_ID: str = "demo-dataset"
    POWER_BI_TABLE_NAME: str = "BiCopilotInsights"
    POWER_BI_TENANT_ID: str | None = None
    POWER_BI_CLIENT_ID: str | None = None
    POWER_BI_CLIENT_SECRET: str | None = None

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

    @model_validator(mode="after")
    def _validate_power_bi_adapter_requirements(self) -> Settings:
        if self.POWER_BI_ADAPTER == "rest" and not (
            self.POWER_BI_TENANT_ID and self.POWER_BI_CLIENT_ID and self.POWER_BI_CLIENT_SECRET
        ):
            raise ValueError(
                "POWER_BI_TENANT_ID, POWER_BI_CLIENT_ID and POWER_BI_CLIENT_SECRET are all "
                "required when POWER_BI_ADAPTER=rest. Use POWER_BI_ADAPTER=mock for local "
                "development and demos without a Microsoft Entra app registration."
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton, loaded and validated once."""
    return Settings()  # values are loaded from the environment / .env at runtime
