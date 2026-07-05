"""
Shared domain type definitions for the MIL Platform Kernel.

This module defines two categories of types:

1. **Typed identifiers** — `NewType` wrappers around `UUID` that give each entity
   its own distinct type at type-check time.  Using separate types prevents
   accidental substitution of, e.g., an `ApplicationId` where an `EvidenceItemId`
   is required, even though both are UUID values at runtime.

2. **Value objects** — immutable `dataclass` types that carry validation logic and
   domain semantics beyond what a primitive can express.  Each value object
   enforces its own invariants in `__post_init__`.

All types here are domain-agnostic infrastructure: they name the entities but
contain no business rules.  Business rules belong in the bounded contexts.

Dependency rule: this module imports only from the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, NewType
from uuid import UUID, uuid4

# ---------------------------------------------------------------------------
# Typed identifiers
#
# Each entity in the domain has its own identifier type.  At runtime they are
# plain UUID values; at type-check time they are distinct, non-interchangeable
# types.  Use the `new_*_id()` factory functions to generate fresh identifiers.
# ---------------------------------------------------------------------------

ApplicationId = NewType("ApplicationId", UUID)
PartyId = NewType("PartyId", UUID)
DocumentId = NewType("DocumentId", UUID)
EvidenceItemId = NewType("EvidenceItemId", UUID)
FindingId = NewType("FindingId", UUID)
VerificationId = NewType("VerificationId", UUID)
PolicyPackId = NewType("PolicyPackId", UUID)
ReviewSessionId = NewType("ReviewSessionId", UUID)
AuditEventId = NewType("AuditEventId", UUID)
WorkflowRunId = NewType("WorkflowRunId", UUID)
TenantId = NewType("TenantId", UUID)
UserId = NewType("UserId", UUID)
RoleId = NewType("RoleId", UUID)


def new_application_id() -> ApplicationId:
    """Return a new random ApplicationId."""
    return ApplicationId(uuid4())


def new_party_id() -> PartyId:
    """Return a new random PartyId."""
    return PartyId(uuid4())


def new_document_id() -> DocumentId:
    """Return a new random DocumentId."""
    return DocumentId(uuid4())


def new_evidence_item_id() -> EvidenceItemId:
    """Return a new random EvidenceItemId."""
    return EvidenceItemId(uuid4())


def new_finding_id() -> FindingId:
    """Return a new random FindingId."""
    return FindingId(uuid4())


def new_verification_id() -> VerificationId:
    """Return a new random VerificationId."""
    return VerificationId(uuid4())


def new_policy_pack_id() -> PolicyPackId:
    """Return a new random PolicyPackId."""
    return PolicyPackId(uuid4())


def new_review_session_id() -> ReviewSessionId:
    """Return a new random ReviewSessionId."""
    return ReviewSessionId(uuid4())


def new_audit_event_id() -> AuditEventId:
    """Return a new random AuditEventId."""
    return AuditEventId(uuid4())


def new_workflow_run_id() -> WorkflowRunId:
    """Return a new random WorkflowRunId."""
    return WorkflowRunId(uuid4())


def new_tenant_id() -> TenantId:
    """Return a new random TenantId."""
    return TenantId(uuid4())


def new_user_id() -> UserId:
    """Return a new random UserId."""
    return UserId(uuid4())


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Money:
    """
    An immutable monetary amount with an ISO 4217 currency code.

    Attributes:
        amount: Non-negative decimal amount.  Uses `Decimal` to avoid
                floating-point rounding errors in financial calculations.
        currency: Three-character ISO 4217 currency code (e.g. "GBP", "USD").
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError(f"amount must be Decimal, got {type(self.amount).__name__}")
        if self.amount < Decimal(0):
            raise ValueError(f"Money amount cannot be negative, got {self.amount}")
        if not self.currency or len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError(f"currency must be a 3-letter ISO 4217 code, got {self.currency!r}")

    @classmethod
    def of(cls, amount: str | Decimal | int, currency: str) -> Money:
        """
        Construct a Money value from a string, Decimal, or integer amount.

        Raises:
            ValueError: If the amount is not a valid decimal or is negative.
        """
        try:
            decimal_amount = Decimal(str(amount))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid monetary amount: {amount!r}") from exc
        return cls(amount=decimal_amount, currency=currency.upper())

    def __str__(self) -> str:
        return f"{self.currency} {self.amount}"


# Confidence label thresholds — not a business rule, just a display convention.
_HIGH_THRESHOLD: Final[float] = 0.85
_MEDIUM_THRESHOLD: Final[float] = 0.60


@dataclass(frozen=True)
class Confidence:
    """
    An extraction or inference confidence score in the closed interval [0.0, 1.0].

    The `label` property maps the numeric score to a human-readable category
    (HIGH, MEDIUM, LOW) for display in reviewer interfaces.  The thresholds are
    fixed by platform convention and do not change per policy.

    Attributes:
        score: Numeric confidence in [0.0, 1.0].
    """

    score: float

    def __post_init__(self) -> None:
        if not isinstance(self.score, (int, float)):
            raise TypeError(f"score must be a number, got {type(self.score).__name__}")
        if not 0.0 <= float(self.score) <= 1.0:
            raise ValueError(f"Confidence score must be in [0.0, 1.0], got {self.score}")

    @property
    def label(self) -> str:
        """Return a human-readable confidence category."""
        if self.score >= _HIGH_THRESHOLD:
            return "HIGH"
        if self.score >= _MEDIUM_THRESHOLD:
            return "MEDIUM"
        return "LOW"

    def __str__(self) -> str:
        return f"{self.score:.0%} ({self.label})"


@dataclass(frozen=True)
class PolicyVersion:
    """
    A semantic version of a Policy Pack.

    Policy Packs are versioned independently of AI models.  Every finding
    records the `PolicyVersion` under which it was generated (Principle XII —
    Deterministic Intelligence).

    Attributes:
        major: Backward-incompatible rule changes increment the major version.
        minor: New rules added in a backward-compatible manner increment minor.
        patch: Corrections or clarifications that do not change rule outcomes.
    """

    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        for name, value in (("major", self.major), ("minor", self.minor), ("patch", self.patch)):
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"PolicyVersion.{name} must be a non-negative integer, got {value!r}"
                )

    @classmethod
    def parse(cls, version_string: str) -> PolicyVersion:
        """
        Parse a semantic version string of the form ``MAJOR.MINOR.PATCH``.

        Raises:
            ValueError: If the string is not in the expected format.
        """
        parts = version_string.strip().split(".")
        if len(parts) != 3:
            raise ValueError(
                f"PolicyVersion must be in MAJOR.MINOR.PATCH format, got {version_string!r}"
            )
        try:
            return cls(major=int(parts[0]), minor=int(parts[1]), patch=int(parts[2]))
        except ValueError as exc:
            raise ValueError(
                f"PolicyVersion components must be integers, got {version_string!r}"
            ) from exc

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def is_compatible_with(self, other: PolicyVersion) -> bool:
        """
        Return True if this version is backward-compatible with ``other``.

        Two versions are compatible when they share the same major version and
        this version is at least as new as ``other``.
        """
        if self.major != other.major:
            return False
        if self.minor != other.minor:
            return self.minor > other.minor
        return self.patch >= other.patch
