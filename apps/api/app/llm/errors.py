"""LLM provider error type -- wraps provider-specific failures (auth, rate
limit, network, refusal, ...) behind one stable exception so callers never
need to know which provider is in use, and no raw provider internals or
credentials leak into logs or client-facing errors."""

from __future__ import annotations


class LLMProviderError(Exception):
    pass
