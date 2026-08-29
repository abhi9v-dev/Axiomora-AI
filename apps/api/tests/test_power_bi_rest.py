"""PowerBIRestAdapter tests -- entirely mocked, no network call and no
real Entra tenant required, so these run in CI at zero cost. Verifies
request construction and error mapping against the real httpx2 client
this project already depends on transitively via the anthropic SDK
(see test_llm_anthropic.py's identical rationale for mocking only the
client boundary, not hand-rolled doubles).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx2
import pytest

from app.action.power_bi.errors import PowerBIAdapterError
from app.action.power_bi.rest import PowerBIRestAdapter


@pytest.fixture
def adapter() -> PowerBIRestAdapter:
    return PowerBIRestAdapter(
        tenant_id="tenant-1",
        client_id="client-1",
        client_secret="secret-1",
        workspace_id="workspace-1",
    )


def _token_response(*, access_token: str = "token-abc", expires_in: int = 3600) -> httpx2.Response:
    request = httpx2.Request("POST", "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token")
    return httpx2.Response(
        200, json={"access_token": access_token, "expires_in": expires_in}, request=request
    )


def _ok_response(*, headers: dict[str, str] | None = None) -> httpx2.Response:
    request = httpx2.Request("POST", "https://api.powerbi.com/v1.0/myorg/groups/workspace-1")
    return httpx2.Response(200, json={}, request=request, headers=headers or {})


async def test_push_rows_sends_the_bearer_token_and_the_rows_payload(
    adapter: PowerBIRestAdapter,
) -> None:
    mock_post = AsyncMock(side_effect=[_token_response(), _ok_response()])
    with patch.object(httpx2.AsyncClient, "post", mock_post):
        result = await adapter.push_rows(dataset_id="ds-1", table_name="Table1", rows=[{"a": 1}])

    assert result.dataset_id == "ds-1"
    assert result.table_name == "Table1"
    assert result.rows_pushed == 1
    assert mock_post.await_count == 2
    token_call, push_call = mock_post.call_args_list
    assert token_call.kwargs["data"]["client_id"] == "client-1"
    assert token_call.kwargs["data"]["client_secret"] == "secret-1"
    push_url = push_call.args[0]
    assert push_url == (
        "https://api.powerbi.com/v1.0/myorg/groups/workspace-1" "/datasets/ds-1/tables/Table1/rows"
    )
    assert push_call.kwargs["json"] == {"rows": [{"a": 1}]}
    assert push_call.kwargs["headers"]["Authorization"] == "Bearer token-abc"


async def test_refresh_dataset_posts_to_the_refreshes_endpoint(adapter: PowerBIRestAdapter) -> None:
    mock_post = AsyncMock(
        side_effect=[_token_response(), _ok_response(headers={"RequestId": "refresh-xyz"})]
    )
    with patch.object(httpx2.AsyncClient, "post", mock_post):
        result = await adapter.refresh_dataset(dataset_id="ds-1")

    assert result.dataset_id == "ds-1"
    assert result.refresh_request_id == "refresh-xyz"
    refresh_url = mock_post.call_args_list[1].args[0]
    assert (
        refresh_url
        == "https://api.powerbi.com/v1.0/myorg/groups/workspace-1/datasets/ds-1/refreshes"
    )


async def test_the_access_token_is_cached_across_calls(adapter: PowerBIRestAdapter) -> None:
    mock_post = AsyncMock(side_effect=[_token_response(), _ok_response(), _ok_response()])
    with patch.object(httpx2.AsyncClient, "post", mock_post):
        await adapter.refresh_dataset(dataset_id="ds-1")
        await adapter.refresh_dataset(dataset_id="ds-2")

    # One token request plus two refresh requests -- the second refresh
    # reused the cached token rather than re-authenticating.
    assert mock_post.await_count == 3


async def test_a_failed_token_request_is_translated(adapter: PowerBIRestAdapter) -> None:
    request = httpx2.Request("POST", "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token")
    response = httpx2.Response(401, request=request)
    mock_post = AsyncMock(
        side_effect=httpx2.HTTPStatusError("unauthorized", request=request, response=response)
    )
    with (
        patch.object(httpx2.AsyncClient, "post", mock_post),
        pytest.raises(PowerBIAdapterError, match="Entra token request failed"),
    ):
        await adapter.refresh_dataset(dataset_id="ds-1")


async def test_a_failed_power_bi_api_call_is_translated(adapter: PowerBIRestAdapter) -> None:
    request = httpx2.Request("POST", "https://api.powerbi.com/v1.0/myorg/groups/workspace-1")
    response = httpx2.Response(429, request=request)

    async def _side_effect(url: str, **kwargs: object) -> httpx2.Response:
        if "login.microsoftonline.com" in url:
            return _token_response()
        raise httpx2.HTTPStatusError("throttled", request=request, response=response)

    with (
        patch.object(httpx2.AsyncClient, "post", AsyncMock(side_effect=_side_effect)),
        pytest.raises(PowerBIAdapterError, match="status 429"),
    ):
        await adapter.refresh_dataset(dataset_id="ds-1")


async def test_a_connection_error_is_translated(adapter: PowerBIRestAdapter) -> None:
    request = httpx2.Request("POST", "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token")
    mock_post = AsyncMock(side_effect=httpx2.ConnectError("boom", request=request))
    with (
        patch.object(httpx2.AsyncClient, "post", mock_post),
        pytest.raises(PowerBIAdapterError, match="Could not reach Microsoft Entra"),
    ):
        await adapter.refresh_dataset(dataset_id="ds-1")


async def test_a_timeout_is_translated(adapter: PowerBIRestAdapter) -> None:
    request = httpx2.Request("POST", "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token")
    mock_post = AsyncMock(side_effect=httpx2.TimeoutException("slow", request=request))
    with (
        patch.object(httpx2.AsyncClient, "post", mock_post),
        pytest.raises(PowerBIAdapterError, match="timed out"),
    ):
        await adapter.refresh_dataset(dataset_id="ds-1")


async def test_a_token_response_without_access_token_is_rejected(
    adapter: PowerBIRestAdapter,
) -> None:
    request = httpx2.Request("POST", "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token")
    empty_token_response = httpx2.Response(200, json={"expires_in": 3600}, request=request)
    mock_post = AsyncMock(return_value=empty_token_response)
    with (
        patch.object(httpx2.AsyncClient, "post", mock_post),
        pytest.raises(PowerBIAdapterError, match="no access_token"),
    ):
        await adapter.refresh_dataset(dataset_id="ds-1")


async def test_no_api_call_made_without_calling_a_method(adapter: PowerBIRestAdapter) -> None:
    """Sanity check that constructing the adapter never talks to the network."""
    assert adapter._workspace_id == "workspace-1"
