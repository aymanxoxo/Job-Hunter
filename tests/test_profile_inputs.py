"""C-007 - BaseProfileInput ABC and text parser contract."""
from __future__ import annotations

import types

import pytest

from core.profile_inputs import BaseProfileInput, TextProfileInput
from tests.contracts.profile_input_contract import assert_profile_input_returns_text


class _DummyProfileInput(BaseProfileInput):
    name = "dummy"

    async def to_text(self, source: object) -> str:
        return str(source)


def test_base_profile_input_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseProfileInput()


def test_subclass_without_to_text_is_abstract():
    class NoToText(BaseProfileInput):
        pass

    with pytest.raises(TypeError):
        NoToText()


def test_base_defaults():
    profile_input = _DummyProfileInput()

    assert profile_input.name == "dummy"
    assert profile_input.accepts == ("text",)


async def test_text_profile_input_returns_input_text_unchanged():
    profile_input = TextProfileInput()
    source = "  Senior Python developer\nseeking remote backend work.  "

    text = await assert_profile_input_returns_text(profile_input, source, expected=source)

    assert text == source
    assert profile_input.name == "text"
    assert profile_input.accepts == ("text",)


async def test_text_profile_input_rejects_non_text_source():
    with pytest.raises(TypeError, match="TextProfileInput expects source to be str"):
        await TextProfileInput().to_text(types.SimpleNamespace(text="profile"))


async def test_contract_helper_rejects_non_string_output():
    class DuckProfileInput(BaseProfileInput):
        async def to_text(self, source: object) -> object:
            return types.SimpleNamespace(text=str(source))

    with pytest.raises(AssertionError):
        await assert_profile_input_returns_text(DuckProfileInput(), "profile")
