from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def test_get_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/app")
    monkeypatch.setenv("WAREHOUSE_URL", "postgresql+asyncpg://u:p@localhost:5432/wh")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.DATABASE_URL == "postgresql+asyncpg://u:p@localhost:5432/app"
    assert settings.LLM_PROVIDER == "fake"
    assert settings.POWER_BI_ENABLED is False
    assert settings.MAX_SQL_REPAIRS == 2

    get_settings.cache_clear()


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()

    assert first is second

    get_settings.cache_clear()


def test_missing_database_url_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("WAREHOUSE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_anthropic_provider_requires_api_key() -> None:
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/app",
            WAREHOUSE_URL="postgresql+asyncpg://u:p@localhost:5432/wh",
            LLM_PROVIDER="anthropic",
            ANTHROPIC_API_KEY=None,
        )


def test_fake_provider_does_not_require_api_key() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/app",
        WAREHOUSE_URL="postgresql+asyncpg://u:p@localhost:5432/wh",
        LLM_PROVIDER="fake",
    )

    assert settings.ANTHROPIC_API_KEY is None


def test_power_bi_defaults_to_the_mock_adapter_disabled() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/app",
        WAREHOUSE_URL="postgresql+asyncpg://u:p@localhost:5432/wh",
    )

    assert settings.POWER_BI_ENABLED is False
    assert settings.POWER_BI_ADAPTER == "mock"


def test_rest_power_bi_adapter_requires_entra_credentials() -> None:
    with pytest.raises(ValidationError, match="POWER_BI_TENANT_ID"):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/app",
            WAREHOUSE_URL="postgresql+asyncpg://u:p@localhost:5432/wh",
            POWER_BI_ADAPTER="rest",
        )


def test_rest_power_bi_adapter_with_all_credentials_is_accepted() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/app",
        WAREHOUSE_URL="postgresql+asyncpg://u:p@localhost:5432/wh",
        POWER_BI_ADAPTER="rest",
        POWER_BI_TENANT_ID="tenant-1",
        POWER_BI_CLIENT_ID="client-1",
        POWER_BI_CLIENT_SECRET="secret-1",
    )

    assert settings.POWER_BI_ADAPTER == "rest"


def test_mock_power_bi_adapter_does_not_require_entra_credentials() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/app",
        WAREHOUSE_URL="postgresql+asyncpg://u:p@localhost:5432/wh",
        POWER_BI_ADAPTER="mock",
    )

    assert settings.POWER_BI_TENANT_ID is None


def test_cors_origins_parses_comma_separated_list() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/app",
        WAREHOUSE_URL="postgresql+asyncpg://u:p@localhost:5432/wh",
        CORS_ORIGINS="http://localhost:3000, http://localhost:3001",
    )

    assert settings.cors_origins == ["http://localhost:3000", "http://localhost:3001"]
