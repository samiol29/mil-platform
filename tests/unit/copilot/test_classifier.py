"""Unit tests for mil.copilot.classifier — QueryClassifier (rule-based, no AI)."""

from __future__ import annotations

from mil.copilot.classifier import classify_query
from mil.copilot.prompts import (
    EXPLAIN_FINDING,
    EXPLAIN_POLICY_RESULT,
    FREEFORM_QUESTION,
    SUMMARIZE_APPLICATION,
)


class TestClassifyQueryFindingKeywords:
    def test_finding_keyword_selects_explain_finding(self) -> None:
        assert classify_query("Why was this finding raised?") == EXPLAIN_FINDING

    def test_flagged_keyword_selects_explain_finding(self) -> None:
        assert classify_query("Why was this application flagged?") == EXPLAIN_FINDING

    def test_case_insensitive(self) -> None:
        assert classify_query("EXPLAIN THIS FINDING") == EXPLAIN_FINDING


class TestClassifyQueryPolicyKeywords:
    def test_policy_keyword_selects_explain_policy_result(self) -> None:
        assert classify_query("Why did this policy fail?") == EXPLAIN_POLICY_RESULT

    def test_rule_keyword_selects_explain_policy_result(self) -> None:
        assert classify_query("Which rule was triggered?") == EXPLAIN_POLICY_RESULT

    def test_compliance_keyword_selects_explain_policy_result(self) -> None:
        assert classify_query("Is this application compliant?") == EXPLAIN_POLICY_RESULT


class TestClassifyQuerySummaryKeywords:
    def test_summarize_keyword_selects_summarize_application(self) -> None:
        assert classify_query("Summarize this application for me.") == SUMMARIZE_APPLICATION

    def test_overview_keyword_selects_summarize_application(self) -> None:
        assert classify_query("Give me an overview.") == SUMMARIZE_APPLICATION

    def test_british_spelling_summarise_matches(self) -> None:
        assert classify_query("Please summarise the case.") == SUMMARIZE_APPLICATION


class TestClassifyQueryFreeformDefault:
    def test_no_keyword_match_defaults_to_freeform(self) -> None:
        assert classify_query("What is the applicant's employer?") == FREEFORM_QUESTION

    def test_empty_string_defaults_to_freeform(self) -> None:
        assert classify_query("") == FREEFORM_QUESTION


class TestClassifyQueryPriorityOrder:
    def test_summary_keyword_wins_over_finding_keyword(self) -> None:
        """Documented fixed priority: summary > finding > policy > freeform."""
        assert classify_query("Summarize the findings") == SUMMARIZE_APPLICATION

    def test_finding_keyword_wins_over_policy_keyword(self) -> None:
        assert classify_query("Did this finding pass?") == EXPLAIN_FINDING


class TestClassifyQueryDeterminism:
    def test_same_input_always_returns_same_output(self) -> None:
        question = "Why was this finding raised?"
        results = {classify_query(question) for _ in range(20)}
        assert results == {EXPLAIN_FINDING}

    def test_returns_a_registered_prompt_identifier(self) -> None:
        from mil.copilot.prompts import list_prompt_ids

        for question in ("Explain this finding.", "Why did this policy fail?", "Summarize it."):
            assert classify_query(question) in list_prompt_ids()
