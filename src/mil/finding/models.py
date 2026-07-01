"""
ORM model for persisted Findings (Finding Management bounded context).

``Finding`` is the durable, immutable record of an AI-generated conclusion
derived from one or more ``EvidenceItem`` rows. It is created once by the
Finding worker and never updated or deleted (append-only, mirroring the
immutability discipline already applied to ``OCRResultRecord`` and
``EvidenceItem``).

Explainability (Engineering Constitution Principle I / III): every Finding
carries five explainability fields — title, rationale, evidence_summary,
confidence_label, recommended_action — and refuses to be constructed if any
of them is empty (``ExplainabilityError``).

Attribution (Principle XII — Deterministic Intelligence): every Finding
records the inference model version, the prompt version, the extraction
version, and the workflow run that produced it. ``policy_pack_id`` is
intentionally omitted this sprint — see ``mil.finding`` package docstring.

Determinism / idempotency (ADR-008): a Finding is identified by the
application it was generated for and the inference model version that
produced it — ``(application_id, model_version)`` is unique. Re-running
Finding generation for the same application under the same model version
cannot produce a second row.

Schema: ``finding`` PostgreSQL schema.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base
from mil.kernel.errors import ExplainabilityError

if TYPE_CHECKING:
    from collections.abc import Sequence

_DEFAULT_LIFECYCLE_STATE = "EXTRACTED"


class Finding(Base):
    """
    Immutable AI-generated conclusion derived from one or more evidence items.

    Created once by the Finding worker and never updated. References the
    application it pertains to and the workflow run that produced it
    (lineage), and carries all five explainability fields plus attribution
    (model version, prompt version, extraction version).
    """

    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "model_version",
            name="uq_findings_application_model_version",
        ),
        {"schema": "finding"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("core.applications.id"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("orchestrator.workflow_runs.id"), nullable=False
    )
    finding_type: Mapped[str] = mapped_column(String(100), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(
        String(50), nullable=False, default=_DEFAULT_LIFECYCLE_STATE
    )
    # Explainability attribute 1: what was found.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # Explainability attribute 2: why it was found.
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    # Explainability attribute 3: what evidence supports it.
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Explainability attribute 4: confidence in plain language.
    confidence_label: Mapped[str] = mapped_column(String(100), nullable=False)
    # Explainability attribute 5: what action the reviewer should take.
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    # Attribution: AI model version.
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    # Attribution: prompt template version.
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    # Attribution: extraction engine version(s) behind the supporting evidence.
    extraction_version: Mapped[str] = mapped_column(String(100), nullable=False)
    # Supporting evidence (record supporting evidence): the exact EvidenceItem
    # ids this Finding was derived from, as JSON-safe strings.
    evidence_item_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        application_id: UUID,
        tenant_id: UUID,
        workflow_run_id: UUID,
        finding_type: str,
        title: str,
        rationale: str,
        evidence_summary: str,
        confidence_label: str,
        recommended_action: str,
        confidence_score: Decimal,
        model_version: str,
        prompt_version: str,
        extraction_version: str,
        evidence_item_ids: Sequence[UUID],
        generated_at: datetime | None = None,
    ) -> Finding:
        """
        Build an immutable Finding.

        Raises:
            ExplainabilityError: If any of the five required explainability
                fields is empty. An incomplete Finding can never be constructed,
                let alone persisted.
        """
        missing = [
            name
            for name, value in (
                ("title", title),
                ("rationale", rationale),
                ("evidence_summary", evidence_summary),
                ("confidence_label", confidence_label),
                ("recommended_action", recommended_action),
            )
            if not value or not value.strip()
        ]
        if missing:
            raise ExplainabilityError(
                f"Finding is missing required explainability field(s): {', '.join(missing)}",
                details={"application_id": str(application_id), "missing_fields": missing},
            )
        if not model_version or not model_version.strip():
            raise ExplainabilityError(
                "Finding is missing required attribution field: model_version",
                details={"application_id": str(application_id)},
            )
        if not prompt_version or not prompt_version.strip():
            raise ExplainabilityError(
                "Finding is missing required attribution field: prompt_version",
                details={"application_id": str(application_id)},
            )
        if not extraction_version or not extraction_version.strip():
            raise ExplainabilityError(
                "Finding is missing required attribution field: extraction_version",
                details={"application_id": str(application_id)},
            )
        if not evidence_item_ids:
            raise ExplainabilityError(
                "Finding must record at least one supporting evidence item",
                details={"application_id": str(application_id)},
            )
        if not (Decimal("0.000") <= confidence_score <= Decimal("1.000")):
            raise ExplainabilityError(
                f"Finding confidence_score must be in [0.000, 1.000], got {confidence_score}",
                details={"application_id": str(application_id)},
            )

        return cls(
            id=uuid4(),
            application_id=application_id,
            tenant_id=tenant_id,
            workflow_run_id=workflow_run_id,
            finding_type=finding_type,
            lifecycle_state=_DEFAULT_LIFECYCLE_STATE,
            title=title,
            rationale=rationale,
            evidence_summary=evidence_summary,
            confidence_label=confidence_label,
            recommended_action=recommended_action,
            confidence_score=confidence_score,
            model_version=model_version,
            prompt_version=prompt_version,
            extraction_version=extraction_version,
            evidence_item_ids=[str(i) for i in evidence_item_ids],
            generated_at=generated_at if generated_at is not None else datetime.now(UTC),
            created_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return (
            f"<Finding id={self.id} application={self.application_id} "
            f"type={self.finding_type} model={self.model_version}>"
        )
