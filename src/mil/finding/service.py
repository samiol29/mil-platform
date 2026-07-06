"""
FindingService — use-case orchestrator for Finding generation.

Creates a ``Finding`` row from an ``InferenceResult`` and the ``EvidenceItem``
rows it was derived from, and emits the ``FINDING_GENERATED`` audit event,
synchronously, in the same database transaction (audit is never routed
through the outbox).

Explainability enforcement (Principle I / III) happens in ``Finding.create``
itself — an incomplete set of explainability fields raises
``ExplainabilityError`` before a row can ever be constructed, so this service
does not duplicate that check.

Policy evaluation does not exist yet (a later sprint): this service produces
one holistic, inference-derived Finding per application per model version, not
one Finding per triggered policy rule. See the ``mil.finding`` package
docstring.

``FindingService`` never evaluates Policy, never performs human review, and
never mutates ``EvidenceItem`` or ``Document`` rows.

Dependency rule: imports only from ``mil.finding``, ``mil.evidence`` (for the
``EvidenceItem`` type, read-only), ``mil.kernel``, and the Python standard
library. No other bounded context is imported.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from mil.finding.models import Finding
from mil.kernel.security import Permission, require_permission
from mil.kernel.types import Confidence

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from mil.audit.writer import AuditWriter
    from mil.evidence.models import EvidenceItem
    from mil.finding.repository import FindingRepository
    from mil.kernel.providers.inference import InferenceResult
    from mil.kernel.security import AuthenticatedUser

_DEFAULT_FINDING_TYPE = "AI_GENERATED_ASSESSMENT"
_DEFAULT_RECOMMENDED_ACTION = (
    "Review the cited evidence and confirm consistency with the application details."
)
_CONFIDENCE_QUANT = Decimal("0.001")


def _average_confidence(evidence_items: Sequence[EvidenceItem]) -> Decimal:
    """
    Derive a Finding's raw confidence score from its supporting evidence.

    No Policy engine exists yet to assign a rule-driven confidence, so the
    score is the mean of the extraction confidences of the evidence items the
    Finding was derived from, rounded to the 3-decimal-place storage precision.
    """
    total = sum((item.extraction_confidence for item in evidence_items), Decimal("0"))
    mean = total / len(evidence_items)
    return mean.quantize(_CONFIDENCE_QUANT, rounding=ROUND_HALF_UP)


def _evidence_summary(evidence_items: Sequence[EvidenceItem]) -> str:
    """Render a plain-text summary of the supporting evidence items."""
    return "; ".join(f"{item.evidence_type}={item.value_text}" for item in evidence_items)


class FindingService:
    """
    Orchestrates Finding creation for the Finding Management bounded context.

    Construct per unit of work with a repository and audit writer bound to the
    active session, so that the Finding and its audit event commit in the same
    transaction as the caller's other writes (the Finding worker's per-job Unit
    of Work).
    """

    def __init__(self, repository: FindingRepository, audit: AuditWriter) -> None:
        self._repo = repository
        self._audit = audit

    def generate_finding(
        self,
        *,
        application_id: UUID,
        tenant_id: UUID,
        workflow_run_id: UUID,
        evidence_items: Sequence[EvidenceItem],
        inference_result: InferenceResult,
        extraction_version: str,
        finding_type: str = _DEFAULT_FINDING_TYPE,
    ) -> Finding:
        """
        Create one immutable ``Finding`` from inference output and its
        supporting evidence, and emit a ``FINDING_GENERATED`` audit event.

        Raises:
            ExplainabilityError: If any required explainability or attribution
                field would be empty (raised by ``Finding.create``).
        """
        confidence_score = _average_confidence(evidence_items)
        finding = Finding.create(
            application_id=application_id,
            tenant_id=tenant_id,
            workflow_run_id=workflow_run_id,
            finding_type=finding_type,
            title=f"AI-Generated Finding: {finding_type}",
            rationale=inference_result.content,
            evidence_summary=_evidence_summary(evidence_items),
            confidence_label=Confidence(score=float(confidence_score)).label,
            recommended_action=_DEFAULT_RECOMMENDED_ACTION,
            confidence_score=confidence_score,
            model_version=inference_result.model_version,
            prompt_version=inference_result.prompt_version,
            extraction_version=extraction_version,
            evidence_item_ids=[item.id for item in evidence_items],
        )
        self._repo.save(finding)
        self._audit.record(
            event_type="FINDING_GENERATED",
            entity_type="FINDING",
            entity_id=finding.id,
            tenant_id=tenant_id,
            application_id=application_id,
            event_data={
                "finding_type": finding.finding_type,
                "model_version": finding.model_version,
                "prompt_version": finding.prompt_version,
                "extraction_version": finding.extraction_version,
                "confidence_score": str(finding.confidence_score),
            },
        )
        return finding

    def list_for_application(
        self, user: AuthenticatedUser, *, application_id: UUID
    ) -> list[Finding]:
        """
        Return every finding for an application, most recent first.

        Raises:
            AuthorizationError: If the user lacks ``read:findings``.
        """
        require_permission(user, Permission.READ_FINDINGS)
        return self._repo.get_for_application(application_id)

    def get_by_id(self, user: AuthenticatedUser, *, finding_id: UUID) -> Finding | None:
        """
        Return the finding with the given id, or ``None`` if not found.

        Raises:
            AuthorizationError: If the user lacks ``read:findings``.
        """
        require_permission(user, Permission.READ_FINDINGS)
        return self._repo.get_by_id(finding_id)
