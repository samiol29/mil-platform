"""Unit tests for mil.copilot.citations — Citation."""

from __future__ import annotations

import pytest

from mil.copilot.citations import (
    APPLICATION,
    EVIDENCE,
    FINDING,
    SUPPORTED_CITATION_KINDS,
    Citation,
)
from mil.kernel.errors import ValidationError


class TestCitationCreate:
    def test_accepts_supported_kind(self) -> None:
        citation = Citation(kind=FINDING, ref="finding-001")
        assert citation.kind == FINDING
        assert citation.ref == "finding-001"

    def test_locator_defaults_to_none(self) -> None:
        assert Citation(kind=APPLICATION, ref="app-001").locator is None

    def test_locator_can_be_set(self) -> None:
        citation = Citation(kind=EVIDENCE, ref="ev-001", locator="page=1")
        assert citation.locator == "page=1"

    def test_rejects_unsupported_kind(self) -> None:
        with pytest.raises(ValidationError):
            Citation(kind="NOT_A_KIND", ref="ref-001")

    def test_rejects_empty_ref(self) -> None:
        with pytest.raises(ValidationError):
            Citation(kind=FINDING, ref="")

    def test_all_supported_kinds_construct(self) -> None:
        for kind in SUPPORTED_CITATION_KINDS:
            assert Citation(kind=kind, ref="ref-001").kind == kind


class TestCitationSerialization:
    def test_to_dict_without_locator(self) -> None:
        citation = Citation(kind=FINDING, ref="finding-001")
        assert citation.to_dict() == {"kind": FINDING, "ref": "finding-001"}

    def test_to_dict_with_locator(self) -> None:
        citation = Citation(kind=EVIDENCE, ref="ev-001", locator="page=2")
        assert citation.to_dict() == {"kind": EVIDENCE, "ref": "ev-001", "locator": "page=2"}

    def test_from_dict_round_trips_without_locator(self) -> None:
        original = Citation(kind=FINDING, ref="finding-001")
        assert Citation.from_dict(original.to_dict()) == original

    def test_from_dict_round_trips_with_locator(self) -> None:
        original = Citation(kind=EVIDENCE, ref="ev-001", locator="page=2")
        assert Citation.from_dict(original.to_dict()) == original

    def test_from_dict_missing_locator_key(self) -> None:
        citation = Citation.from_dict({"kind": APPLICATION, "ref": "app-001"})
        assert citation.locator is None
