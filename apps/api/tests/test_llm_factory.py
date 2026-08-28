from __future__ import annotations

from typing import Literal

from app.config import Settings
from app.llm.anthropic_provider import AnthropicLLMProvider
from app.llm.factory import get_llm_provider
from app.llm.fake import FakeLLMProvider


def _settings(
    *,
    llm_provider: Literal["fake", "anthropic"] = "fake",
    anthropic_api_key: str | None = None,
    llm_model: str = "claude-opus-5",
) -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/app",
        WAREHOUSE_URL="postgresql+asyncpg://u:p@localhost:5432/wh",
        LLM_PROVIDER=llm_provider,
        ANTHROPIC_API_KEY=anthropic_api_key,
        LLM_MODEL=llm_model,
    )


def test_returns_fake_provider_by_default() -> None:
    provider = get_llm_provider(_settings())

    assert isinstance(provider, FakeLLMProvider)


def test_returns_anthropic_provider_when_configured() -> None:
    settings = _settings(
        llm_provider="anthropic", anthropic_api_key="sk-test", llm_model="claude-opus-5"
    )

    provider = get_llm_provider(settings)

    assert isinstance(provider, AnthropicLLMProvider)
    assert provider._model == "claude-opus-5"
