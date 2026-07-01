"""
Canonical error hierarchy and API error response schema for the MIL Platform.

All exceptions raised by MIL bounded contexts derive from `MILError`.  The
hierarchy is structured so callers can catch at whatever granularity they need:

    except DomainError:          # any business rule violation
    except NotFoundError:        # specific entity-not-found case
    except MILError:             # any MIL exception including auth, infra

`ErrorCode` provides stable string constants so API clients can match error
responses without parsing human-readable messages.

`APIErrorResponse` is the canonical Pydantic schema for error responses
returned by all MIL HTTP endpoints.

Dependency rule: this module imports only from the Python standard library and
from Pydantic (a core platform dependency).  It MUST NOT import from other
kernel modules to avoid circular imports.
"""

from __future__ import annotations

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------


class ErrorCode:
    """
    Stable string constants for canonical MIL error codes.

    API clients should match error responses by code, not by message.  Messages
    may change; codes are versioned and stable across patch releases.
    """

    # --- Domain errors (business rule violations) --------------------------
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    CONFLICT = "CONFLICT"

    # --- Evidence & finding integrity errors --------------------------------
    EVIDENCE_PROVENANCE_INCOMPLETE = "EVIDENCE_PROVENANCE_INCOMPLETE"
    FINDING_EXPLAINABILITY_INCOMPLETE = "FINDING_EXPLAINABILITY_INCOMPLETE"
    EVIDENCE_SCOPE_VIOLATION = "EVIDENCE_SCOPE_VIOLATION"

    # --- Policy errors ------------------------------------------------------
    POLICY_EVALUATION_FAILED = "POLICY_EVALUATION_FAILED"

    # --- Authentication / authorisation errors ------------------------------
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"

    # --- Provider errors (OCR, extraction, inference, storage) -------------
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_VERSION_MISSING = "PROVIDER_VERSION_MISSING"

    # --- Audit integrity errors ---------------------------------------------
    AUDIT_WRITE_FAILED = "AUDIT_WRITE_FAILED"

    # --- Infrastructure / DI errors ----------------------------------------
    DEPENDENCY_NOT_REGISTERED = "DEPENDENCY_NOT_REGISTERED"


# ---------------------------------------------------------------------------
# Base exception
# ---------------------------------------------------------------------------


class MILError(Exception):
    """
    Base class for all exceptions raised by the MIL platform.

    Every MIL exception carries a stable ``code`` (from ``ErrorCode``) and an
    optional ``details`` dict for structured diagnostic information.  The
    human-readable ``message`` is the exception message string.
    """

    def __init__(
        self,
        message: str,
        code: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details: dict[str, object] = details or {}


# ---------------------------------------------------------------------------
# Domain errors — business rule violations
# ---------------------------------------------------------------------------


class DomainError(MILError):
    """
    A business rule or domain invariant has been violated.

    Raise `DomainError` (or a subclass) when the request is syntactically valid
    but cannot be fulfilled because it would break a domain rule.  HTTP
    endpoints typically map `DomainError` to a 422 Unprocessable Entity response.
    """


class NotFoundError(DomainError):
    """The requested entity does not exist or is not visible to the caller."""

    def __init__(
        self,
        entity_type: str,
        entity_id: object,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=f"{entity_type} not found: {entity_id}",
            code=ErrorCode.NOT_FOUND,
            details={"entity_type": entity_type, "entity_id": str(entity_id), **(details or {})},
        )


class ValidationError(DomainError):
    """Input data failed domain validation."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        resolved_details: dict[str, object] = details or {}
        if field is not None:
            resolved_details = {"field": field, **resolved_details}
        super().__init__(
            message=message, code=ErrorCode.VALIDATION_FAILED, details=resolved_details
        )


class InvalidStateTransitionError(DomainError):
    """
    The requested lifecycle state transition is not permitted.

    Used by the Finding lifecycle state machine and any other bounded context
    that enforces a defined state graph.
    """

    def __init__(
        self,
        entity_type: str,
        entity_id: object,
        from_state: str,
        to_state: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=(
                f"Cannot transition {entity_type} {entity_id} from '{from_state}' to '{to_state}'"
            ),
            code=ErrorCode.INVALID_STATE_TRANSITION,
            details={
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "from_state": from_state,
                "to_state": to_state,
                **(details or {}),
            },
        )


class ConflictError(DomainError):
    """The current resource state prevents the requested operation."""

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message=message, code=ErrorCode.CONFLICT, details=details)


# ---------------------------------------------------------------------------
# Evidence & finding integrity errors
# ---------------------------------------------------------------------------


class ProvenanceError(DomainError):
    """
    An evidence item is missing one or more required provenance attributes.

    Provenance is non-negotiable: every EvidenceItem must record where it came
    from, how it was extracted, and under which model and prompt versions
    (Engineering Constitution, Principle XII).
    """

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.EVIDENCE_PROVENANCE_INCOMPLETE,
            details=details,
        )


class ExplainabilityError(DomainError):
    """
    A Finding is missing one or more required explainability fields.

    Every Finding must answer: what was found, why, what evidence supports it,
    how confident is the finding, and what action is recommended.
    """

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.FINDING_EXPLAINABILITY_INCOMPLETE,
            details=details,
        )


class PolicyEvaluationError(DomainError):
    """
    A Policy evaluation could not be completed or produced an incomplete result.

    Raised when no active Policy Pack exists for a tenant, or when a
    ``PolicyEvaluationResult`` is missing a required attribution field
    (``policy_version``, ``outcome``). Policy evaluation is non-negotiable:
    every ``PolicyResult`` must record which pack version produced it
    (Engineering Constitution, Principle XII).
    """

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.POLICY_EVALUATION_FAILED,
            details=details,
        )


class ScopeViolationError(DomainError):
    """
    Access to data outside the caller's permitted scope was attempted.

    Raised when a request tries to read evidence or findings from an application
    that belongs to a different tenant, or that the caller is not authorised
    to access.  Distinct from `AuthorizationError` in that scope violations are
    about data boundaries, not permission checks.
    """

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.EVIDENCE_SCOPE_VIOLATION,
            details=details,
        )


# ---------------------------------------------------------------------------
# Authentication and authorisation errors
# ---------------------------------------------------------------------------


class AuthenticationError(MILError):
    """The request did not supply valid authentication credentials."""

    def __init__(
        self,
        message: str = "Authentication required",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.AUTHENTICATION_REQUIRED,
            details=details,
        )


class AuthorizationError(MILError):
    """The authenticated principal lacks the required permissions."""

    def __init__(
        self,
        message: str,
        required_permission: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        resolved_details: dict[str, object] = details or {}
        if required_permission is not None:
            resolved_details = {"required_permission": required_permission, **resolved_details}
        super().__init__(
            message=message,
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            details=resolved_details,
        )


# ---------------------------------------------------------------------------
# Provider errors
# ---------------------------------------------------------------------------


class ProviderError(MILError):
    """
    An external intelligence provider (OCR, extraction, inference, storage) failed.

    ``retryable`` declares, at the source of the failure, whether the platform
    may safely retry the operation (ADR-008: retryable-vs-terminal classification
    is a property of the failure, not a hard-coded list in the orchestrator).
    A generic provider failure is treated as transient and therefore retryable
    by default; structural contract violations override this to ``False``.
    """

    def __init__(
        self,
        message: str,
        provider_name: str | None = None,
        details: dict[str, object] | None = None,
        *,
        retryable: bool = True,
    ) -> None:
        resolved_details: dict[str, object] = details or {}
        if provider_name is not None:
            resolved_details = {"provider_name": provider_name, **resolved_details}
        super().__init__(
            message=message,
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            details=resolved_details,
        )
        self.retryable = retryable


class ProviderVersionMissingError(ProviderError):
    """
    The provider response is missing required version attribution.

    Every provider that produces AI output MUST return a version identifier
    (model version, prompt version, extraction version) so the platform can
    satisfy Principle XII — Deterministic Intelligence.  This error is raised
    when a registered provider violates that contract.

    This is a structural contract violation, not a transient fault: retrying
    cannot fix it, so it is terminal (``retryable=False``).
    """

    def __init__(self, provider_name: str, missing_field: str) -> None:
        super().__init__(
            message=(
                f"Provider '{provider_name}' returned a response without "
                f"required version field '{missing_field}'"
            ),
            provider_name=provider_name,
            details={"missing_field": missing_field},
            retryable=False,
        )
        self.code = ErrorCode.PROVIDER_VERSION_MISSING


# ---------------------------------------------------------------------------
# Audit errors
# ---------------------------------------------------------------------------


class AuditWriteError(MILError):
    """
    An audit event could not be written.

    This is a critical platform error.  The application must treat an audit
    write failure as a hard stop — never silently discard audit events.
    """

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.AUDIT_WRITE_FAILED,
            details=details,
        )


# ---------------------------------------------------------------------------
# Infrastructure errors
# ---------------------------------------------------------------------------


class DependencyNotRegisteredError(MILError):
    """
    The requested dependency has not been registered in the DI container.

    Raised by `Container.resolve()` when no binding exists for the requested
    interface type.
    """

    def __init__(self, interface: type[object]) -> None:
        super().__init__(
            message=f"No binding registered for interface '{interface.__qualname__}'",
            code=ErrorCode.DEPENDENCY_NOT_REGISTERED,
            details={"interface": interface.__qualname__},
        )


# ---------------------------------------------------------------------------
# API error response schema
# ---------------------------------------------------------------------------


class APIErrorDetail(BaseModel):
    """A single field-level error detail, used in validation error responses."""

    field: str
    message: str


class APIErrorResponse(BaseModel):
    """
    Canonical API error response body.

    All MIL HTTP endpoints return this schema for error responses.  API clients
    should match on ``code`` (a stable ``ErrorCode`` constant) rather than on
    ``message`` (which may change across releases).
    """

    code: str
    message: str
    request_id: str | None = None
    details: list[APIErrorDetail] = []
