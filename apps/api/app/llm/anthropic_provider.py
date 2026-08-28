"""Real Claude API provider.

Calling this incurs real, metered cost -- see docs/04_TRT.md's cost
strategy; never assume it's free. Only constructed when
LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY is set (app.config.Settings
validates that combination at startup, before this class is ever built).

Uses a plain text completion (not the SDK's structured-output helpers):
app.nl2sql.agent owns JSON parsing, schema validation and the one
formatting retry, so the same logic applies uniformly to every provider,
including FakeLLMProvider.
"""

from __future__ import annotations

import anthropic

from app.llm.errors import LLMProviderError

DEFAULT_MAX_TOKENS = 4096


class AnthropicLLMProvider:
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, *, system: str, user: str) -> str:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": "medium"},
            )
        except anthropic.RateLimitError as exc:
            raise LLMProviderError("Claude API rate limit exceeded") from exc
        except anthropic.NotFoundError as exc:
            raise LLMProviderError(f"Unknown Claude model {self._model!r}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMProviderError("Could not reach the Claude API") from exc
        except anthropic.APIStatusError as exc:
            raise LLMProviderError(f"Claude API error (status {exc.status_code})") from exc

        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            raise LLMProviderError(f"Claude declined to respond (refusal, category={category})")

        for block in response.content:
            if block.type == "text":
                return block.text

        raise LLMProviderError("Claude API response contained no text content")
