"""LLMProvider interface: the only way the rest of the app talks to a
language model (ADR 0002: provider interfaces for external dependencies).

Deliberately minimal and provider-agnostic -- callers own prompt
construction and response validation (see app.nl2sql.agent), so the same
JSON-parsing and retry logic works unchanged against FakeLLMProvider or a
real provider. The model never receives credentials or database/action
access; it only ever sees text and returns text.
"""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    async def complete(self, *, system: str, user: str) -> str:
        """Return the model's raw text completion for one system+user turn."""
        ...
