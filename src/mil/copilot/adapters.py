"""
Query Port adapters — composition-root wiring for the Copilot bounded
context (ADR-010, US2 Sprint 7C).

Each adapter class wraps an existing bounded-context repository and presents
it through the corresponding read-only Query Port Protocol declared in
``mil.copilot.ports``. This is the one module in the ``copilot`` package
permitted to reference other bounded contexts' repository and model types —
it is composition-root code, in the same spirit as ``workers/*.py``
composition roots and ``mil.api.deps.get_finding_trigger``.

These adapters are constructed exclusively from ``mil.api.deps.get_copilot_service``
— never from within ``mil.copilot.service`` or ``mil.copilot.ports``, which
must continue to depend only on the Protocol/view types, not on this module
or the repositories it wraps.

Each adapter takes an already-constructed repository instance (not a raw
database session) — this keeps the adapters trivially unit-testable with a
fake or mocked repository, and keeps session/AuditWriter construction as a
composition-root (``deps.py``) concern rather than an adapter concern.

Mapping notes (ORM row -> read-only View):

- ``Document``: ``DocumentView.document_type``/``filename``/``status`` map
  from ``mime_type``/``original_filename``/``ingestion_status`` respectively
  — Sprint 3D stores the business document classification as ``mime_type``
  (see ``mil.api.v1.schemas.DocumentResponse``); this adapter mirrors that
  existing shim rather than inventing a new one.
- ``EvidenceItem``: ``confidence`` is derived from the ``Decimal``
  ``extraction_confidence`` column; ``field_location`` is stored as a JSON
  dict (``page_number``/``field_name``/``bounding_box``) and is reduced to
  its ``field_name`` string (or ``None``) to match ``EvidenceView``'s shape.
- ``PolicyResult``: has no ``rule_ref``/``rationale`` columns — it records
  ``outcome`` and a list of ``triggered_rule_keys``. This adapter synthesizes
  both: ``rule_ref`` is the comma-joined rule keys (or a fixed sentinel when
  none triggered), and ``rationale`` is a short, deterministic sentence built
  from ``outcome`` and those keys. No new columns or policy semantics are
  introduced — this is presentation-only synthesis for Copilot grounding.

Dependency rule: this module (uniquely, within ``mil.copilot``) type-references
``mil.application``, ``mil.document``, ``mil.evidence``, ``mil.finding``,
``mil.policy``, and ``mil.review`` — all under ``TYPE_CHECKING`` only, since
no adapter instantiates a repository itself (the composition root does).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.copilot.ports import (
    ApplicationView,
    DocumentTextView,
    DocumentView,
    EvidenceView,
    FindingView,
    PolicyResultView,
    ReviewActionView,
    ReviewCommentView,
    ReviewSessionView,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from mil.application.models import MortgageApplication
    from mil.application.repository import ApplicationRepository
    from mil.document.models import Document
    from mil.document.ocr_models import OCRResultRecord
    from mil.document.ocr_repository import OCRResultRepository
    from mil.document.repository import DocumentRepository
    from mil.evidence.models import EvidenceItem
    from mil.evidence.repository import EvidenceRepository
    from mil.finding.models import Finding
    from mil.finding.repository import FindingRepository
    from mil.policy.models import PolicyResult
    from mil.policy.repository import PolicyRepository
    from mil.review.models import ReviewAction, ReviewComment, ReviewSession
    from mil.review.repository import ReviewRepository

_NO_TRIGGERED_RULES = "N/A"


# ---------------------------------------------------------------------------
# ORM row -> read-only View mapping helpers
# ---------------------------------------------------------------------------


def _to_application_view(application: MortgageApplication) -> ApplicationView:
    return ApplicationView(
        id=application.id,
        tenant_id=application.tenant_id,
        status=application.status,
        created_at=application.created_at,
    )


def _to_document_view(document: Document) -> DocumentView:
    return DocumentView(
        id=document.id,
        application_id=document.application_id,
        document_type=document.mime_type,
        filename=document.original_filename,
        status=document.ingestion_status,
        created_at=document.uploaded_at,
    )


def _to_document_text_view(document_id: UUID, record: OCRResultRecord) -> DocumentTextView:
    return DocumentTextView(
        document_id=document_id,
        provider_version=record.provider_version,
        page_count=record.page_count,
        full_text=record.full_text,
        processed_at=record.processed_at,
    )


def _to_evidence_view(item: EvidenceItem) -> EvidenceView:
    field_name = item.field_location.get("field_name") if item.field_location else None
    field_location = str(field_name) if field_name is not None else None
    return EvidenceView(
        id=item.id,
        application_id=item.application_id,
        document_id=item.document_id,
        evidence_type=item.evidence_type,
        value_text=item.value_text or "",
        confidence=float(item.extraction_confidence),
        page_number=item.page_number or 0,
        field_location=field_location,
        extraction_method=item.extraction_method,
        extraction_model_version=item.extraction_model_version,
        extracted_at=item.extracted_at,
    )


def _to_finding_view(finding: Finding) -> FindingView:
    return FindingView(
        id=finding.id,
        application_id=finding.application_id,
        finding_type=finding.finding_type,
        title=finding.title,
        rationale=finding.rationale,
        evidence_summary=finding.evidence_summary,
        confidence_label=finding.confidence_label,
        recommended_action=finding.recommended_action,
        model_version=finding.model_version,
        prompt_version=finding.prompt_version,
        extraction_version=finding.extraction_version,
        created_at=finding.created_at,
    )


def _to_policy_result_view(result: PolicyResult) -> PolicyResultView:
    rule_ref = (
        ", ".join(result.triggered_rule_keys)
        if result.triggered_rule_keys
        else (_NO_TRIGGERED_RULES)
    )
    rationale = (
        f"Outcome: {result.outcome}; triggered rules: {rule_ref}"
        if result.triggered_rule_keys
        else f"Outcome: {result.outcome}; no rules triggered"
    )
    return PolicyResultView(
        id=result.id,
        finding_id=result.finding_id,
        policy_version=result.policy_version,
        rule_ref=rule_ref,
        status=result.outcome,
        rationale=rationale,
        evaluated_at=result.evaluated_at,
    )


def _to_review_session_view(session: ReviewSession) -> ReviewSessionView:
    return ReviewSessionView(
        id=session.id,
        finding_id=session.finding_id,
        application_id=session.application_id,
        status=session.status,
        assigned_reviewer_id=session.assigned_reviewer_id,
        created_at=session.created_at,
        closed_at=session.closed_at,
    )


def _to_review_action_view(action: ReviewAction) -> ReviewActionView:
    return ReviewActionView(
        id=action.id,
        review_session_id=action.review_session_id,
        action_type=action.action_type,
        actor_user_id=action.actor_user_id,
        actor_type=action.actor_type,
        previous_status=action.previous_status,
        new_status=action.new_status,
        reason=action.reason,
        previous_value=action.previous_value,
        new_value=action.new_value,
        created_at=action.created_at,
    )


def _to_review_comment_view(comment: ReviewComment) -> ReviewCommentView:
    return ReviewCommentView(
        id=comment.id,
        review_session_id=comment.review_session_id,
        author_user_id=comment.author_user_id,
        comment_text=comment.comment_text,
        created_at=comment.created_at,
    )


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


class ApplicationReaderAdapter:
    """Adapts ``ApplicationRepository`` to the ``ApplicationReader`` port."""

    def __init__(self, repository: ApplicationRepository) -> None:
        self._repo = repository

    def get_by_id(self, application_id: UUID) -> ApplicationView | None:
        application = self._repo.get_by_id(application_id)
        return _to_application_view(application) if application is not None else None


class DocumentReaderAdapter:
    """Adapts ``DocumentRepository`` to the ``DocumentReader`` port."""

    def __init__(self, repository: DocumentRepository) -> None:
        self._repo = repository

    def get_for_application(self, application_id: UUID) -> Sequence[DocumentView]:
        return tuple(_to_document_view(d) for d in self._repo.get_for_application(application_id))


class DocumentTextReaderAdapter:
    """
    Adapts ``DocumentRepository`` + ``OCRResultRepository`` to the
    ``DocumentTextReader`` port.

    Unlike the other adapters, this one wraps two repositories: it must first
    find which documents belong to the application (``DocumentRepository``),
    then load each document's persisted raw text (``OCRResultRepository``).
    Documents with no OCR result yet (still PENDING) are silently skipped —
    Copilot grounds on whatever governed text already exists, never on
    in-flight or absent extraction.
    """

    def __init__(self, documents: DocumentRepository, ocr_results: OCRResultRepository) -> None:
        self._documents = documents
        self._ocr_results = ocr_results

    def get_for_application(self, application_id: UUID) -> Sequence[DocumentTextView]:
        views: list[DocumentTextView] = []
        for document in self._documents.get_for_application(application_id):
            records = self._ocr_results.get_for_document(document.id)
            if not records:
                continue
            # get_for_document orders most-recent-first; the first row is the
            # current persisted text for this document.
            views.append(_to_document_text_view(document.id, records[0]))
        return tuple(views)


class EvidenceReaderAdapter:
    """Adapts ``EvidenceRepository`` to the ``EvidenceReader`` port."""

    def __init__(self, repository: EvidenceRepository) -> None:
        self._repo = repository

    def get_for_application(self, application_id: UUID) -> Sequence[EvidenceView]:
        return tuple(_to_evidence_view(e) for e in self._repo.get_for_application(application_id))


class FindingReaderAdapter:
    """Adapts ``FindingRepository`` to the ``FindingReader`` port."""

    def __init__(self, repository: FindingRepository) -> None:
        self._repo = repository

    def get_for_application(self, application_id: UUID) -> Sequence[FindingView]:
        return tuple(_to_finding_view(f) for f in self._repo.get_for_application(application_id))

    def get_by_id(self, finding_id: UUID) -> FindingView | None:
        finding = self._repo.get_by_id(finding_id)
        return _to_finding_view(finding) if finding is not None else None


class PolicyResultReaderAdapter:
    """
    Adapts ``PolicyRepository`` to the ``PolicyResultReader`` port.

    See the module docstring for the ``rule_ref``/``rationale`` synthesis
    this adapter performs, since ``PolicyResult`` carries no such columns.
    """

    def __init__(self, repository: PolicyRepository) -> None:
        self._repo = repository

    def get_for_finding(self, finding_id: UUID) -> Sequence[PolicyResultView]:
        return tuple(
            _to_policy_result_view(result) for result in self._repo.get_for_finding(finding_id)
        )


class ReviewReaderAdapter:
    """Adapts ``ReviewRepository`` to the ``ReviewReader`` port."""

    def __init__(self, repository: ReviewRepository) -> None:
        self._repo = repository

    def get_session_for_finding(self, finding_id: UUID) -> ReviewSessionView | None:
        session = self._repo.get_session_for_finding(finding_id)
        return _to_review_session_view(session) if session is not None else None

    def get_actions_for_session(self, review_session_id: UUID) -> Sequence[ReviewActionView]:
        return tuple(
            _to_review_action_view(action)
            for action in self._repo.get_actions_for_session(review_session_id)
        )

    def get_comments_for_session(self, review_session_id: UUID) -> Sequence[ReviewCommentView]:
        return tuple(
            _to_review_comment_view(comment)
            for comment in self._repo.get_comments_for_session(review_session_id)
        )
