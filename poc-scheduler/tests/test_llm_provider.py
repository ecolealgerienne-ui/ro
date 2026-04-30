"""Tests de la couche LLM (provider, parsing, types)."""

from __future__ import annotations

import pytest

from src.llm import (
    FakeLLMProvider,
    LLMParseError,
    Message,
    Role,
    extract_json_block,
)

# ---------- Types ----------


def test_message_requires_non_empty_content() -> None:
    with pytest.raises(ValueError):
        Message(role=Role.USER, content="")


def test_role_values() -> None:
    assert Role.USER.value == "user"
    assert Role.SYSTEM.value == "system"
    assert Role.ASSISTANT.value == "assistant"


# ---------- FakeLLMProvider ----------


def test_fake_provider_returns_canned_responses_in_order() -> None:
    provider = FakeLLMProvider(responses=["first", "second"])
    msgs = [Message(role=Role.USER, content="hello")]
    assert provider.complete(msgs) == "first"
    assert provider.complete(msgs) == "second"


def test_fake_provider_raises_when_responses_exhausted() -> None:
    provider = FakeLLMProvider(responses=["only"])
    msgs = [Message(role=Role.USER, content="x")]
    provider.complete(msgs)
    with pytest.raises(RuntimeError, match=r"plus de reponses"):
        provider.complete(msgs)


def test_fake_provider_callable() -> None:
    provider = FakeLLMProvider(responses=lambda messages: f"echo({len(messages)})")
    out = provider.complete([Message(role=Role.USER, content="hi")])
    assert out == "echo(1)"


def test_fake_provider_records_calls() -> None:
    provider = FakeLLMProvider(responses=["x"])
    msg = Message(role=Role.USER, content="hello")
    provider.complete([msg])
    assert len(provider.calls) == 1
    assert provider.calls[0] == [msg]


# ---------- extract_json_block ----------


def test_extract_pure_json() -> None:
    assert extract_json_block('{"a": 1}') == {"a": 1}


def test_extract_json_in_fence() -> None:
    raw = 'Voici la reponse :\n```json\n{"x": 42}\n```\nfin.'
    assert extract_json_block(raw) == {"x": 42}


def test_extract_json_in_unmarked_fence() -> None:
    raw = "```\n[1, 2, 3]\n```"
    assert extract_json_block(raw) == [1, 2, 3]


def test_extract_first_balanced_object_when_surrounded_by_prose() -> None:
    raw = 'Bien sur. Voici : {"a": 1, "b": [2, 3]} et c\'est fini.'
    assert extract_json_block(raw) == {"a": 1, "b": [2, 3]}


def test_extract_handles_nested_objects() -> None:
    raw = 'prefix {"outer": {"inner": {"k": "v"}}} suffix'
    assert extract_json_block(raw) == {"outer": {"inner": {"k": "v"}}}


def test_extract_handles_strings_with_braces() -> None:
    raw = '{"text": "a } b { c"}'
    assert extract_json_block(raw) == {"text": "a } b { c"}


def test_extract_raises_on_invalid_content() -> None:
    with pytest.raises(LLMParseError):
        extract_json_block("nothing here")


def test_extract_raises_on_empty() -> None:
    with pytest.raises(LLMParseError, match=r"vide"):
        extract_json_block("   ")
