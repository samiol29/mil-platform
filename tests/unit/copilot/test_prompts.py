"""Unit tests for mil.copilot.prompts — the prompt identifier/version registry."""

from __future__ import annotations

import pytest

from mil.copilot.prompts import (
    EXPLAIN_FINDING,
    FREEFORM_QUESTION,
    get_prompt_version,
    list_prompt_ids,
)
from mil.kernel.errors import ValidationError


class TestGetPromptVersion:
    def test_returns_version_for_registered_id(self) -> None:
        assert get_prompt_version(EXPLAIN_FINDING) == "explain-finding-v1"

    def test_raises_for_unknown_id(self) -> None:
        with pytest.raises(ValidationError):
            get_prompt_version("NOT_REGISTERED")

    def test_no_prompt_text_leaks_into_version(self) -> None:
        for prompt_id in list_prompt_ids():
            version = get_prompt_version(prompt_id)
            assert " " not in version


class TestListPromptIds:
    def test_includes_known_identifiers(self) -> None:
        ids = list_prompt_ids()
        assert EXPLAIN_FINDING in ids
        assert FREEFORM_QUESTION in ids

    def test_every_id_has_a_version(self) -> None:
        for prompt_id in list_prompt_ids():
            assert get_prompt_version(prompt_id)
