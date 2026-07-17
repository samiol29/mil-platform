"""
Citation — reusable, provider-agnostic citation abstraction (ADR-011 §6).

Every substantive claim a future Copilot response makes must cite a governed
record: an Application, Document, Evidence item, Finding, PolicyResult, or
ReviewAction. ``Citation`` is the single, uniform shape for such a reference,
independent of which ``InferenceProvider`` produced the response.

This module defines only the citation *data shape* and its validation. It
performs no rendering, formatting, or display logic — that belongs to
whatever presentation layer eventually consumes a ``CopilotResponse``.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from mil.kernel.errors import ValidationError

if TYPE_CHECKING:
    from collections.abc import Mapping

# ---------------------------------------------------------------------------
# Citation kinds
#
# This taxonomy is deliberately owned by the Copilot bounded context, not the
# kernel (ARCHITECTURE.md §4; ADR-011). ``mil.kernel.providers.inference``
# knows only an opaque ``GroundingItem.kind`` string; Copilot is the one
# place that names what a "Finding" or "PolicyResult" citation means.
# ---------------------------------------------------------------------------

APPLICATION = "APPLICATION"
PARTY = "PARTY"
DOCUMENT = "DOCUMENT"
DOCUMENT_TEXT = "DOCUMENT_TEXT"
EVIDENCE = "EVIDENCE"
FINDING = "FINDING"
POLICY_RESULT = "POLICY_RESULT"
REVIEW_ACTION = "REVIEW_ACTION"

SUPPORTED_CITATION_KINDS: frozenset[str] = frozenset(
    {APPLICATION, PARTY, DOCUMENT, DOCUMENT_TEXT, EVIDENCE, FINDING, POLICY_RESULT, REVIEW_ACTION}
)


@dataclasses.dataclass(frozen=True)
class Citation:
    """
    A single, provider-agnostic reference to a governed record.

    Attributes:
        kind:    One of ``SUPPORTED_CITATION_KINDS`` — the category of
                 record being cited.
        ref:     The stable identifier of the cited record (e.g. an
                 ``evidence_ref`` or a UUID rendered as ``str``).
        locator: Optional finer-grained pointer within the record (e.g. a
                 page number or field name), preserving Principle II
                 provenance where applicable.
    """

    kind: str
    ref: str
    locator: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in SUPPORTED_CITATION_KINDS:
            raise ValidationError(
                f"Unsupported citation kind: {self.kind!r}",
                field="kind",
                details={"supported_kinds": sorted(SUPPORTED_CITATION_KINDS)},
            )
        if not self.ref:
            raise ValidationError("ref must not be empty", field="ref")

    def to_dict(self) -> dict[str, str]:
        """Serialise to a JSON-safe dict for persistence."""
        data: dict[str, str] = {"kind": self.kind, "ref": self.ref}
        if self.locator is not None:
            data["locator"] = self.locator
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Citation:
        """Deserialise from the JSON-safe dict produced by ``to_dict``."""
        locator = data.get("locator")
        return cls(
            kind=str(data["kind"]),
            ref=str(data["ref"]),
            locator=str(locator) if locator is not None else None,
        )
