"""Deterministic, zero-cost LLMProvider for development and tests.

Generic and reusable -- not NL2SQL-specific. Returns pre-registered canned
responses matched by a substring of the `user` prompt, so any component
built on LLMProvider can configure exactly the scenarios its tests need
without a network call or API cost.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class FakeLLMProvider:
    default_response: str = "{}"
    _rules: list[tuple[str, deque[str]]] = field(default_factory=list)
    calls: list[tuple[str, str]] = field(default_factory=list)

    def register(self, match: str, *responses: str) -> None:
        """Whenever a future `user` prompt contains `match` as a substring,
        return `responses` in order, repeating the last one once the queue
        is exhausted. Multiple queued responses let a test exercise a retry
        path -- e.g. register("Buyer department", "not json", '{"sql": "..."}').
        Rules are checked in registration order; the first substring match
        wins.
        """
        self._rules.append((match, deque(responses)))

    async def complete(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        for match, queue in self._rules:
            if match in user:
                if len(queue) > 1:
                    return queue.popleft()
                return queue[0] if queue else self.default_response
        return self.default_response
