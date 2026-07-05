"""
ORM models for the Policy bounded context.

Three entities:

- ``PolicyPack`` — a versioned collection of verification rules governing how
  evidence and findings are evaluated (Engineering Constitution Principle
  IX). Mutable lifecycle metadata (activate/deactivate); at most one pack may
  be active per tenant at a time.
- ``PolicyRule`` — a single rule belonging to a Policy Pack. Static catalogue
  data; ``mil.policy`` never hardcodes verification logic — a rule's actual
  triggering logic lives in the registered ``PolicyProvider`` implementation.
- ``PolicyResult`` — the durable, immutable record of one Policy evaluation of
  one Finding. Created once by the Policy worker and never updated
  (append-only, mirroring the immutability discipline already applied to
  ``EvidenceItem`` and ``Finding``).

Schema: ``policy`` PostgreSQL schema (dedicated bounded-context schema,
mirroring ``evidence`` and ``finding`` — see migration 0007 docstring for why
this differs from the ``core.policy_packs`` placement in the earlier target
data model).

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base
from mil.kernel.errors import ConflictError, PolicyEvaluationError, ValidationError

if TYPE_CHECKING:
    from mil.kernel.providers.policy import PolicyEvaluationResult


class PolicyPack(Base):
    """
    A versioned collection of verification rules governing evidence and
    Finding evaluation for a tenant.

    At most one pack may be active (``activated_at`` set, ``deactivated_at``
    unset) per tenant at any time — enforced here at the aggregate level and
    backed by a partial unique index (migration 0007).
    """

    __tablename__ = "policy_packs"
    __table_args__ = ({"schema": "policy"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("core.users.id"), nullable=True)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        version: str,
        name: str,
        content_hash: str,
        jurisdiction: str | None = None,
        created_by: UUID | None = None,
    ) -> PolicyPack:
        """Create a new, inactive Policy Pack (``activated_at`` is unset)."""
        if not version or not version.strip():
            raise ValidationError("version must not be empty", field="version")
        if not name or not name.strip():
            raise ValidationError("name must not be empty", field="name")
        if not content_hash or not content_hash.strip():
            raise ValidationError("content_hash must not be empty", field="content_hash")

        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            version=version.strip(),
            name=name.strip(),
            jurisdiction=jurisdiction,
            content_hash=content_hash.strip(),
            activated_at=None,
            deactivated_at=None,
            created_at=datetime.now(UTC),
            created_by=created_by,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def activate(self) -> None:
        """
        Activate this pack.

        Raises:
            ConflictError: If this pack is already active or has been
                deactivated (a deactivated pack cannot be reactivated —
                create a new version instead).
        """
        if self.deactivated_at is not None:
            raise ConflictError(
                f"PolicyPack {self.id} has been deactivated and cannot be reactivated"
            )
        if self.activated_at is not None:
            raise ConflictError(f"PolicyPack {self.id} is already active")
        self.activated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        """
        Deactivate this pack.

        Raises:
            ConflictError: If this pack was never activated or is already
                deactivated.
        """
        if self.activated_at is None:
            raise ConflictError(f"PolicyPack {self.id} was never activated")
        if self.deactivated_at is not None:
            raise ConflictError(f"PolicyPack {self.id} is already deactivated")
        self.deactivated_at = datetime.now(UTC)

    @property
    def is_active(self) -> bool:
        """Return ``True`` if this pack is currently active."""
        return self.activated_at is not None and self.deactivated_at is None

    def __repr__(self) -> str:
        return f"<PolicyPack id={self.id} version={self.version} active={self.is_active}>"


class PolicyRule(Base):
    """
    A single rule belonging to a Policy Pack — static catalogue data.

    ``mil.policy`` never hardcodes verification logic: a rule's actual
    triggering condition is evaluated by the registered ``PolicyProvider``,
    which receives this rule's ``rule_key``/``severity``/``description`` as a
    domain-agnostic ``PolicyRuleDefinition`` (never the ORM row itself).
    """

    __tablename__ = "policy_rules"
    __table_args__ = (
        UniqueConstraint("policy_pack_id", "rule_key", name="uq_policy_rules_pack_rule_key"),
        {"schema": "policy"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    policy_pack_id: Mapped[UUID] = mapped_column(
        ForeignKey("policy.policy_packs.id"), nullable=False
    )
    rule_key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def create(
        cls,
        *,
        policy_pack_id: UUID,
        rule_key: str,
        name: str,
        description: str,
        severity: str,
    ) -> PolicyRule:
        if not rule_key or not rule_key.strip():
            raise ValidationError("rule_key must not be empty", field="rule_key")
        if not name or not name.strip():
            raise ValidationError("name must not be empty", field="name")
        if not severity or not severity.strip():
            raise ValidationError("severity must not be empty", field="severity")

        return cls(
            id=uuid4(),
            policy_pack_id=policy_pack_id,
            rule_key=rule_key.strip(),
            name=name.strip(),
            description=description,
            severity=severity.strip(),
            created_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return f"<PolicyRule id={self.id} pack={self.policy_pack_id} key={self.rule_key}>"


class PolicyResult(Base):
    """
    Immutable persisted outcome of one Policy evaluation of one Finding.

    Created once by the Policy worker and never updated. References the
    Finding evaluated, the application and workflow run it belongs to, and
    the Policy Pack and provider version the evaluation ran under.

    Determinism / idempotency (ADR-008): a result is identified by the
    Finding it evaluated and the Policy provider version that produced it —
    ``(finding_id, policy_version)`` is unique. Re-running evaluation for the
    same Finding under the same policy version cannot produce a duplicate row.
    """

    __tablename__ = "policy_results"
    __table_args__ = (
        UniqueConstraint("finding_id", "policy_version", name="uq_policy_results_finding_version"),
        {"schema": "policy"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    finding_id: Mapped[UUID] = mapped_column(ForeignKey("finding.findings.id"), nullable=False)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("core.applications.id"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("orchestrator.workflow_runs.id"), nullable=False
    )
    policy_pack_id: Mapped[UUID] = mapped_column(
        ForeignKey("policy.policy_packs.id"), nullable=False
    )
    # Attribution: the PolicyProvider version that produced this result.
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    # Rule keys triggered by this evaluation (JSON-safe strings; empty when none).
    triggered_rule_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        finding_id: UUID,
        application_id: UUID,
        tenant_id: UUID,
        workflow_run_id: UUID,
        policy_pack_id: UUID,
        result: PolicyEvaluationResult,
    ) -> PolicyResult:
        """
        Build an immutable Policy result from a provider ``PolicyEvaluationResult``.

        Raises:
            PolicyEvaluationError: If ``result`` is missing required
                attribution (``outcome``, ``policy_version``). An incomplete
                result can never be constructed, let alone persisted.
        """
        if not result.outcome or not result.outcome.strip():
            raise PolicyEvaluationError(
                "PolicyEvaluationResult is missing required field: outcome",
                details={"finding_id": str(finding_id)},
            )
        if not result.policy_version or not result.policy_version.strip():
            raise PolicyEvaluationError(
                "PolicyEvaluationResult is missing required field: policy_version",
                details={"finding_id": str(finding_id)},
            )

        return cls(
            id=uuid4(),
            finding_id=finding_id,
            application_id=application_id,
            tenant_id=tenant_id,
            workflow_run_id=workflow_run_id,
            policy_pack_id=policy_pack_id,
            policy_version=result.policy_version,
            outcome=result.outcome,
            triggered_rule_keys=[r.rule_key for r in result.triggered_rules],
            evaluated_at=result.evaluated_at,
            created_at=datetime.now(UTC),
        )

    @property
    def is_flagged(self) -> bool:
        """Return ``True`` if this result triggered at least one rule."""
        return bool(self.triggered_rule_keys)

    def __repr__(self) -> str:
        return (
            f"<PolicyResult id={self.id} finding={self.finding_id} "
            f"outcome={self.outcome} version={self.policy_version}>"
        )
