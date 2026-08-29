"""get_power_bi_adapter(settings) -- selects the PowerBIAdapter
implementation the same way app.llm.factory.get_llm_provider and
app.embeddings.factory.get_embedding_provider select theirs.

Re-checks the POWER_BI_ADAPTER=rest credential requirement that
app.config.Settings already validates at startup -- defense in depth, the
same pattern get_llm_provider already applies to ANTHROPIC_API_KEY.
"""

from __future__ import annotations

from app.action.power_bi.base import PowerBIAdapter
from app.action.power_bi.mock import MockPowerBIAdapter
from app.action.power_bi.rest import PowerBIRestAdapter
from app.config import Settings


def get_power_bi_adapter(settings: Settings) -> PowerBIAdapter:
    if settings.POWER_BI_ADAPTER == "mock":
        return MockPowerBIAdapter()
    if settings.POWER_BI_ADAPTER == "rest":
        if not (
            settings.POWER_BI_TENANT_ID
            and settings.POWER_BI_CLIENT_ID
            and settings.POWER_BI_CLIENT_SECRET
        ):
            raise ValueError(
                "POWER_BI_TENANT_ID, POWER_BI_CLIENT_ID and POWER_BI_CLIENT_SECRET are all "
                "required when POWER_BI_ADAPTER=rest"
            )
        return PowerBIRestAdapter(
            tenant_id=settings.POWER_BI_TENANT_ID,
            client_id=settings.POWER_BI_CLIENT_ID,
            client_secret=settings.POWER_BI_CLIENT_SECRET,
            workspace_id=settings.POWER_BI_WORKSPACE_ID,
        )
    raise ValueError(f"Unsupported POWER_BI_ADAPTER={settings.POWER_BI_ADAPTER!r}")
