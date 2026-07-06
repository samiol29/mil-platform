"""
EvidenceService — use-case orchestrator for evidence creation.

Creates ``EvidenceItem`` rows from ``ExtractionProvider`` output and emits the
``EVIDENCE_CREATED`` audit event for each item, synchronously, in the same
database transaction (audit is never routed through the outbox).

Provenance enforcement (Principle II / Principle XII) happens in
``EvidenceItem.create`` itself — an incomplete ``EvidenceAttributes`` object
raises ``ProvenanceError`` before a row can ever be constructed, so this
service does not duplicate that check.

``EvidenceService`` never evaluates Policy and never invokes an
``InferenceProvider``. It has no knowledge of Findings.

Dependency rule: imports only from ``mil.evidence``, ``mil.kernel``, and the
Python standard library. No other bounded context is imported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.evidence.models import EvidenceItem
from mil.kernel.security import Permission, require_permission

if TYPE_CHECKING:
    from uuid import UUID

    from mil.audit.writer import AuditWriter
    from mil.evidence.repository import EvidenceRepository
    from mil.kernel.providers.extraction import EvidenceAttributes
    from mil.kernel.security import AuthenticatedUser


class EvidenceService:
    """
    Orchestrates evidence item creation for the Evidence Management bounded
    context.

    Construct per unit of work with a repository and audit writer bound to the
    active session, so that every evidence item and its audit event commit in
    the same transaction as the caller's other writes (the Extraction worker's
    per-job Unit of Work).
    """

    def __init__(self, repository: EvidenceRepository, audit: AuditWriter) -> None:
        self._repo = repository
        self._audit = audit

    def create_evidence_items(
        self,
        *,
        application_id: UUID,
        document_id: UUID,
        workflow_run_id: UUID,
        tenant_id: UUID,
        attrs_list: list[EvidenceAttributes],
        party_id: UUID | None = None,
    ) -> list[EvidenceItem]:
        """
        Create one immutable ``EvidenceItem`` per ``EvidenceAttributes`` and
        emit an ``EVIDENCE_CREATED`` audit event for each.

        Raises:
            ProvenanceError: If any ``EvidenceAttributes`` object is missing a
                required provenance attribute (raised by ``EvidenceItem.create``).
        """
        created: list[EvidenceItem] = []
        for attrs in attrs_list:
            item = EvidenceItem.create(
                application_id=application_id,
                document_id=document_id,
                workflow_run_id=workflow_run_id,
                tenant_id=tenant_id,
                attrs=attrs,
                party_id=party_id,
            )
            self._repo.save(item)
            self._audit.record(
                event_type="EVIDENCE_CREATED",
                entity_type="EVIDENCE_ITEM",
                entity_id=item.id,
                tenant_id=tenant_id,
                application_id=application_id,
                event_data={
                    "evidence_type": item.evidence_type,
                    "document_id": str(document_id),
                    "extraction_model_version": item.extraction_model_version,
                    "extraction_confidence": str(item.extraction_confidence),
                },
            )
            created.append(item)
        return created

    def list_for_application(
        self, user: AuthenticatedUser, *, application_id: UUID
    ) -> list[EvidenceItem]:
        """
        Return every evidence item for an application, most recent first.

        Raises:
            AuthorizationError: If the user lacks ``read:evidence``.
        """
        require_permission(user, Permission.READ_EVIDENCE)
        return self._repo.get_for_application(application_id)
