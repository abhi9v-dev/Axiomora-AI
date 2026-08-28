from __future__ import annotations

from app.llm.fake import FakeLLMProvider


async def test_returns_default_response_when_nothing_registered() -> None:
    provider = FakeLLMProvider()

    result = await provider.complete(system="sys", user="anything")

    assert result == "{}"


async def test_returns_custom_default_response() -> None:
    provider = FakeLLMProvider(default_response="fallback text")

    result = await provider.complete(system="sys", user="anything")

    assert result == "fallback text"


async def test_matches_by_substring_of_user_prompt() -> None:
    provider = FakeLLMProvider()
    provider.register("hold time", '{"sql": "SELECT 1"}')

    result = await provider.complete(system="sys", user="Why did median hold time spike in Q2?")

    assert result == '{"sql": "SELECT 1"}'


async def test_non_matching_prompt_falls_back_to_default() -> None:
    provider = FakeLLMProvider()
    provider.register("hold time", '{"sql": "SELECT 1"}')

    result = await provider.complete(system="sys", user="completely unrelated question")

    assert result == "{}"


async def test_multiple_responses_are_returned_in_order_then_repeat_last() -> None:
    provider = FakeLLMProvider()
    provider.register("retry me", "first", "second")

    assert await provider.complete(system="s", user="retry me please") == "first"
    assert await provider.complete(system="s", user="retry me please") == "second"
    # Queue exhausted after the second call -- keep returning the last one.
    assert await provider.complete(system="s", user="retry me please") == "second"


async def test_first_matching_rule_wins_in_registration_order() -> None:
    provider = FakeLLMProvider()
    provider.register("task", "first rule")
    provider.register("task hold time", "second rule")

    result = await provider.complete(system="s", user="task hold time question")

    assert result == "first rule"


async def test_records_every_call() -> None:
    provider = FakeLLMProvider()

    await provider.complete(system="sys-a", user="user-a")
    await provider.complete(system="sys-b", user="user-b")

    assert provider.calls == [("sys-a", "user-a"), ("sys-b", "user-b")]
