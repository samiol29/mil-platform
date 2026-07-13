"""Unit tests for mil.cross_application_intelligence.service — pure derivation functions."""

from __future__ import annotations

from uuid import uuid4

from mil.cross_application_intelligence.service import (
    DocumentSignal,
    FindingSignal,
    find_repeated_finding_types,
    find_reused_documents,
    summarize_review_outcomes,
)


class TestFindReusedDocuments:
    def test_flags_shared_hash_across_applications(self) -> None:
        app_a, app_b = uuid4(), uuid4()
        shared_hash = "a" * 64
        docs = [
            DocumentSignal(uuid4(), app_a, shared_hash, "paystub.pdf"),
            DocumentSignal(uuid4(), app_b, shared_hash, "paystub.pdf"),
        ]
        observations = find_reused_documents(docs)
        assert len(observations) == 1
        assert observations[0].kind == "REUSED_DOCUMENT"
        assert set(observations[0].application_ids) == {app_a, app_b}
        assert len(observations[0].document_ids) == 2

    def test_ignores_duplicate_within_same_application(self) -> None:
        app_a = uuid4()
        shared_hash = "b" * 64
        docs = [
            DocumentSignal(uuid4(), app_a, shared_hash, "a.pdf"),
            DocumentSignal(uuid4(), app_a, shared_hash, "a-copy.pdf"),
        ]
        assert find_reused_documents(docs) == []

    def test_no_observation_for_unique_hashes(self) -> None:
        docs = [
            DocumentSignal(uuid4(), uuid4(), "c" * 64, "a.pdf"),
            DocumentSignal(uuid4(), uuid4(), "d" * 64, "b.pdf"),
        ]
        assert find_reused_documents(docs) == []


class TestFindRepeatedFindingTypes:
    def test_flags_type_across_applications(self) -> None:
        app_a, app_b = uuid4(), uuid4()
        findings = [
            FindingSignal(uuid4(), app_a, "INCOME_MISMATCH", "unreviewed"),
            FindingSignal(uuid4(), app_b, "INCOME_MISMATCH", "verified"),
        ]
        observations = find_repeated_finding_types(findings)
        assert len(observations) == 1
        assert observations[0].kind == "REPEATED_FINDING_TYPE"
        assert set(observations[0].application_ids) == {app_a, app_b}

    def test_ignores_single_application(self) -> None:
        app_a = uuid4()
        findings = [
            FindingSignal(uuid4(), app_a, "INCOME_MISMATCH", "unreviewed"),
            FindingSignal(uuid4(), app_a, "INCOME_MISMATCH", "verified"),
        ]
        assert find_repeated_finding_types(findings) == []


class TestSummarizeReviewOutcomes:
    def test_returns_none_for_no_findings(self) -> None:
        assert summarize_review_outcomes([]) is None

    def test_summarizes_counts_across_applications(self) -> None:
        app_a, app_b = uuid4(), uuid4()
        findings = [
            FindingSignal(uuid4(), app_a, "TYPE_A", "verified"),
            FindingSignal(uuid4(), app_a, "TYPE_B", "overridden"),
            FindingSignal(uuid4(), app_b, "TYPE_A", "escalated"),
        ]
        observation = summarize_review_outcomes(findings)
        assert observation is not None
        assert observation.kind == "REVIEW_OUTCOME_SUMMARY"
        assert set(observation.application_ids) == {app_a, app_b}
        assert len(observation.finding_ids) == 3
