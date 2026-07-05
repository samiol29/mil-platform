"""
Prompt Registry — versioned prompt identifiers for the Copilot (ADR-011 §7).

This module implements *only* the identifier and version-lookup surface a
future Copilot service needs to pin a prompt version per response
(Engineering Constitution Principle XII — Deterministic Intelligence). It
does **not** contain any prompt text or template content — prompt authoring
is a Sprint 7B concern, reviewed separately from this structural registry.

A prompt version is a versioned, code-resident identifier: changing which
version an intent maps to is a reviewable code change, never a silent runtime
mutation (ADR-011 §7).

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

from mil.kernel.errors import ValidationError

# ---------------------------------------------------------------------------
# Prompt identifiers
#
# One identifier per Copilot intent. Sprint 7B will map each identifier to
# an actual template; Sprint 7A registers only the identifier and its pinned
# version string.
# ---------------------------------------------------------------------------

EXPLAIN_FINDING = "EXPLAIN_FINDING"
EXPLAIN_POLICY_RESULT = "EXPLAIN_POLICY_RESULT"
SUMMARIZE_APPLICATION = "SUMMARIZE_APPLICATION"
FREEFORM_QUESTION = "FREEFORM_QUESTION"

_PROMPT_VERSIONS: dict[str, str] = {
    EXPLAIN_FINDING: "explain-finding-v1",
    EXPLAIN_POLICY_RESULT: "explain-policy-result-v1",
    SUMMARIZE_APPLICATION: "summarize-application-v1",
    FREEFORM_QUESTION: "freeform-question-v1",
}


def get_prompt_version(prompt_id: str) -> str:
    """
    Look up the pinned prompt version for a registered prompt identifier.

    Raises:
        ValidationError: If ``prompt_id`` is not registered.
    """
    try:
        return _PROMPT_VERSIONS[prompt_id]
    except KeyError:
        raise ValidationError(
            f"Unknown prompt identifier: {prompt_id!r}",
            field="prompt_id",
            details={"registered_prompt_ids": sorted(_PROMPT_VERSIONS)},
        ) from None


def list_prompt_ids() -> tuple[str, ...]:
    """Return every registered prompt identifier."""
    return tuple(_PROMPT_VERSIONS)
