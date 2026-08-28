"""Selects an LLMProvider implementation from Settings.LLM_PROVIDER."""

from __future__ import annotations

from app.config import Settings
from app.llm.anthropic_provider import AnthropicLLMProvider
from app.llm.base import LLMProvider
from app.llm.fake import FakeLLMProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    if settings.LLM_PROVIDER == "fake":
        return FakeLLMProvider()
    if settings.LLM_PROVIDER == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return AnthropicLLMProvider(api_key=settings.ANTHROPIC_API_KEY, model=settings.LLM_MODEL)
    raise ValueError(f"Unsupported LLM_PROVIDER={settings.LLM_PROVIDER!r}")
