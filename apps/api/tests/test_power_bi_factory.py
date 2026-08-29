"""app.action.power_bi.factory.get_power_bi_adapter -- mirrors
test_llm_factory.py's style for get_llm_provider."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.action.power_bi.factory import get_power_bi_adapter
from app.action.power_bi.mock import MockPowerBIAdapter
from app.action.power_bi.rest import PowerBIRestAdapter
from app.config import Settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/app",
        "WAREHOUSE_URL": "postgresql+asyncpg://u:p@localhost:5432/wh",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_returns_mock_adapter_by_default() -> None:
    adapter = get_power_bi_adapter(_settings())

    assert isinstance(adapter, MockPowerBIAdapter)


def test_returns_rest_adapter_when_configured_with_credentials() -> None:
    settings = _settings(
        POWER_BI_ADAPTER="rest",
        POWER_BI_TENANT_ID="tenant-1",
        POWER_BI_CLIENT_ID="client-1",
        POWER_BI_CLIENT_SECRET="secret-1",
        POWER_BI_WORKSPACE_ID="workspace-1",
    )

    adapter = get_power_bi_adapter(settings)

    assert isinstance(adapter, PowerBIRestAdapter)
    assert adapter._workspace_id == "workspace-1"


def test_settings_itself_rejects_rest_adapter_without_credentials() -> None:
    # app.config.Settings validates this combination at startup, mirroring
    # ANTHROPIC_API_KEY's requirement for LLM_PROVIDER=anthropic.
    with pytest.raises(ValidationError, match="POWER_BI_TENANT_ID"):
        _settings(POWER_BI_ADAPTER="rest")


def test_factory_re_checks_credentials_as_defense_in_depth() -> None:
    # Bypasses Settings' own model_validator (model_construct skips
    # validation entirely) to exercise the factory's own defensive
    # re-check directly -- the same belt-and-suspenders pattern
    # app.llm.factory.get_llm_provider already applies to ANTHROPIC_API_KEY.
    settings = Settings.model_construct(
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/app",
        WAREHOUSE_URL="postgresql+asyncpg://u:p@localhost:5432/wh",
        POWER_BI_ADAPTER="rest",
        POWER_BI_TENANT_ID=None,
        POWER_BI_CLIENT_ID=None,
        POWER_BI_CLIENT_SECRET=None,
    )

    with pytest.raises(ValueError, match="POWER_BI_TENANT_ID"):
        get_power_bi_adapter(settings)
