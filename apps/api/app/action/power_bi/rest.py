"""Real Power BI REST adapter, authenticating via a Microsoft Entra app
registration's client-credentials OAuth2 flow.

Calling this incurs a real network dependency on Microsoft Entra ID and
the Power BI REST API and requires tenant/workspace/dataset setup and
licensing (docs/09_DEPLOYMENT_OPERATIONS.md's "Power BI reality check") --
never assume it succeeds or is free of operational risk. Only constructed
when POWER_BI_ENABLED=true and POWER_BI_ADAPTER=rest with all three Entra
credentials set (app.config.Settings validates that combination at
startup, before this class is ever built, mirroring
AnthropicLLMProvider's ANTHROPIC_API_KEY requirement).

Uses httpx2 (this project's installed HTTP client) directly rather than
the Power BI/MSAL SDKs, keeping the dependency surface identical to what
app.llm.anthropic_provider already relies on transitively.
"""

from __future__ import annotations

import time

import httpx2

from app.action.power_bi.base import PowerBIPushResult, PowerBIRefreshResult
from app.action.power_bi.errors import PowerBIAdapterError

_AUTHORITY = "https://login.microsoftonline.com"
_POWER_BI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
_POWER_BI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
_REQUEST_TIMEOUT_SECONDS = 30.0
# Refresh the cached token a little before its actual expiry to avoid a
# request racing against the token expiring mid-flight.
_TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS = 60


class PowerBIRestAdapter:
    def __init__(
        self, *, tenant_id: str, client_id: str, client_secret: str, workspace_id: str
    ) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._workspace_id = workspace_id
        self._cached_token: str | None = None
        self._cached_token_expires_at: float = 0.0

    async def _get_access_token(self) -> str:
        if self._cached_token is not None and time.monotonic() < self._cached_token_expires_at:
            return self._cached_token

        token_url = f"{_AUTHORITY}/{self._tenant_id}/oauth2/v2.0/token"
        try:
            async with httpx2.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "scope": _POWER_BI_SCOPE,
                    },
                )
                response.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            raise PowerBIAdapterError(
                f"Microsoft Entra token request failed (status {exc.response.status_code})"
            ) from exc
        except httpx2.TimeoutException as exc:
            raise PowerBIAdapterError("Microsoft Entra token request timed out") from exc
        except httpx2.RequestError as exc:
            raise PowerBIAdapterError("Could not reach Microsoft Entra ID") from exc

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise PowerBIAdapterError("Microsoft Entra token response contained no access_token")

        expires_in = float(payload.get("expires_in", 0))
        self._cached_token = token
        self._cached_token_expires_at = (
            time.monotonic() + expires_in - _TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS
        )
        return str(token)

    async def _post(self, path: str, *, json_body: dict[str, object]) -> httpx2.Response:
        token = await self._get_access_token()
        url = f"{_POWER_BI_API_BASE}/groups/{self._workspace_id}{path}"
        try:
            async with httpx2.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    url,
                    json=json_body,
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            raise PowerBIAdapterError(
                f"Power BI API request to {path} failed (status {exc.response.status_code})"
            ) from exc
        except httpx2.TimeoutException as exc:
            raise PowerBIAdapterError(f"Power BI API request to {path} timed out") from exc
        except httpx2.RequestError as exc:
            raise PowerBIAdapterError(f"Could not reach the Power BI API for {path}") from exc
        return response

    async def push_rows(
        self, *, dataset_id: str, table_name: str, rows: list[dict[str, object]]
    ) -> PowerBIPushResult:
        await self._post(
            f"/datasets/{dataset_id}/tables/{table_name}/rows", json_body={"rows": rows}
        )
        return PowerBIPushResult(
            dataset_id=dataset_id, table_name=table_name, rows_pushed=len(rows)
        )

    async def refresh_dataset(self, *, dataset_id: str) -> PowerBIRefreshResult:
        response = await self._post(f"/datasets/{dataset_id}/refreshes", json_body={})
        # Power BI returns the new refresh's ID in the Location header
        # (POST /refreshes has an empty body on success), not JSON.
        location = response.headers.get("RequestId") or response.headers.get("Location") or ""
        refresh_request_id = location.rstrip("/").rsplit("/", 1)[-1] or "unknown"
        return PowerBIRefreshResult(dataset_id=dataset_id, refresh_request_id=refresh_request_id)
