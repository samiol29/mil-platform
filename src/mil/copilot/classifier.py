"""
QueryClassifier — deterministic, rule-based prompt selection (US2 Sprint 7C).

Maps a reviewer's natural-language question to one of the prompt identifiers
registered in ``mil.copilot.prompts``, using fixed keyword rules evaluated in
a documented priority order. This is explicitly **not** an AI classifier —
no model call, no embeddings, no hidden state, no randomness. Given the same
question text, ``classify_query`` always returns the same identifier
(Principle XII — determinism; ADR-011 — no hidden reasoning).

If no rule matches, ``FREEFORM_QUESTION`` is the deterministic default —
every question is classifiable; there is no "unclassified" outcome.

Dependency rule: imports only from ``mil.copilot.prompts`` and the Python
standard library.
"""

from __future__ import annotations

from mil.copilot.prompts import (
    EXPLAIN_FINDING,
    EXPLAIN_POLICY_RESULT,
    FREEFORM_QUESTION,
    SUMMARIZE_APPLICATION,
)

# ---------------------------------------------------------------------------
# Rules, in fixed priority order (first match wins). Each tuple pairs a
# prompt identifier with the keywords that select it. Keyword matching is
# case-insensitive substring matching against the lower-cased question text.
# ---------------------------------------------------------------------------

_SUMMARY_KEYWORDS: tuple[str, ...] = ("summarize", "summarise", "summary", "overview")
_FINDING_KEYWORDS: tuple[str, ...] = ("finding", "findings", "flagged", "flag")
_POLICY_KEYWORDS: tuple[str, ...] = (
    "policy",
    "policies",
    "rule",
    "complian",  # matches both "compliance" and "compliant"
    "pass",
    "fail",
    "passed",
    "failed",
)

_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (SUMMARIZE_APPLICATION, _SUMMARY_KEYWORDS),
    (EXPLAIN_FINDING, _FINDING_KEYWORDS),
    (EXPLAIN_POLICY_RESULT, _POLICY_KEYWORDS),
)


def classify_query(question_text: str) -> str:
    """
    Return the prompt identifier for ``question_text``.

    Rules are evaluated in the fixed order: summarization keywords, then
    finding keywords, then policy keywords. The first matching rule wins.
    ``FREEFORM_QUESTION`` is returned when no rule matches.

    This function is pure and deterministic: it has no side effects, makes
    no external calls, and depends on nothing but its input.
    """
    normalized = question_text.lower()
    for prompt_id, keywords in _RULES:
        if any(keyword in normalized for keyword in keywords):
            return prompt_id
    return FREEFORM_QUESTION
