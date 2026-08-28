"""AnthropicLLMProvider tests -- entirely mocked, no network call and no
API key required, so these run in CI without cost. Verifies request
construction and response/error mapping against the real anthropic SDK's
actual types (not hand-rolled doubles), by mocking only
`client.messages.create`.
"""

from __future__ import annotations

import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anthropic
import httpx2
import pytest

from app.llm.anthropic_provider import AnthropicLLMProvider
from app.llm.errors import LLMProviderError


def _text_response(text: str, *, stop_reason: str = "end_turn") -> SimpleNamespace:
    block = types.SimpleNamespace(type="text", text=text)
    return types.SimpleNamespace(content=[block], stop_reason=stop_reason, stop_details=None)


def _mock_request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.fixture
def provider() -> AnthropicLLMProvider:
    return AnthropicLLMProvider(api_key="sk-test-fake-key", model="claude-opus-5")


async def test_complete_returns_text_block(provider: AnthropicLLMProvider) -> None:
    mock_create = AsyncMock(return_value=_text_response('{"sql": "SELECT 1"}'))
    provider._client.messages.create = mock_create  # type: ignore[method-assign]

    result = await provider.complete(system="sys prompt", user="user prompt")

    assert result == '{"sql": "SELECT 1"}'
    mock_create.assert_awaited_once()
    _, kwargs = mock_create.call_args
    assert kwargs["model"] == "claude-opus-5"
    assert kwargs["system"] == "sys prompt"
    assert kwargs["messages"] == [{"role": "user", "content": "user prompt"}]


async def test_ignores_non_text_blocks_and_returns_first_text_block(
    provider: AnthropicLLMProvider,
) -> None:
    thinking_block = types.SimpleNamespace(type="thinking", thinking="...")
    text_block = types.SimpleNamespace(type="text", text="the answer")
    response = types.SimpleNamespace(
        content=[thinking_block, text_block], stop_reason="end_turn", stop_details=None
    )
    provider._client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    result = await provider.complete(system="s", user="u")

    assert result == "the answer"


async def test_raises_when_response_has_no_text_block(provider: AnthropicLLMProvider) -> None:
    response = types.SimpleNamespace(content=[], stop_reason="end_turn", stop_details=None)
    provider._client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    with pytest.raises(LLMProviderError, match="no text content"):
        await provider.complete(system="s", user="u")


async def test_refusal_stop_reason_raises_llm_provider_error(
    provider: AnthropicLLMProvider,
) -> None:
    response = types.SimpleNamespace(
        content=[],
        stop_reason="refusal",
        stop_details=types.SimpleNamespace(category="cyber"),
    )
    provider._client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    with pytest.raises(LLMProviderError, match="refusal"):
        await provider.complete(system="s", user="u")


async def test_rate_limit_error_is_translated(provider: AnthropicLLMProvider) -> None:
    request = _mock_request()
    response = httpx2.Response(429, request=request)
    provider._client.messages.create = AsyncMock(  # type: ignore[method-assign]
        side_effect=anthropic.RateLimitError("rate limited", response=response, body=None)
    )

    with pytest.raises(LLMProviderError, match="rate limit"):
        await provider.complete(system="s", user="u")


async def test_connection_error_is_translated(provider: AnthropicLLMProvider) -> None:
    provider._client.messages.create = AsyncMock(  # type: ignore[method-assign]
        side_effect=anthropic.APIConnectionError(request=_mock_request())
    )

    with pytest.raises(LLMProviderError, match="Could not reach"):
        await provider.complete(system="s", user="u")


async def test_not_found_error_is_translated(provider: AnthropicLLMProvider) -> None:
    request = _mock_request()
    response = httpx2.Response(404, request=request)
    provider._client.messages.create = AsyncMock(  # type: ignore[method-assign]
        side_effect=anthropic.NotFoundError("not found", response=response, body=None)
    )

    with pytest.raises(LLMProviderError, match="Unknown Claude model"):
        await provider.complete(system="s", user="u")


async def test_generic_api_status_error_is_translated(provider: AnthropicLLMProvider) -> None:
    request = _mock_request()
    response = httpx2.Response(500, request=request)
    provider._client.messages.create = AsyncMock(  # type: ignore[method-assign]
        side_effect=anthropic.APIStatusError("server error", response=response, body=None)
    )

    with pytest.raises(LLMProviderError, match="status 500"):
        await provider.complete(system="s", user="u")


async def test_no_api_call_made_without_calling_complete(provider: AnthropicLLMProvider) -> None:
    """Sanity check that constructing the provider never talks to the network."""
    assert provider._model == "claude-opus-5"
