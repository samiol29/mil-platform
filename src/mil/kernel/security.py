"""
Authentication context types and RBAC primitives for the MIL Platform.

This module defines:

- ``AuthenticatedUser`` — the immutable principal context populated by the
  Zero Trust authentication middleware (T021) and carried through the request
  lifecycle via a context variable.

- ``Role`` — the set of RBAC roles defined in the MIL platform, matching the
  target user categories in the product specification.

- ``Permission`` — granular permission constants used for access control checks
  across all bounded contexts.

- ``ROLE_PERMISSIONS`` — the default permission mapping that determines which
  permissions each role holds.  This mapping reflects the platform's access
  model; it is defined here in the kernel so all bounded contexts share a
  single, consistent source of truth.

- Helper functions ``has_role``, ``has_permission``, and ``require_permission``
  for performing access control checks in service-layer code.

The Zero Trust middleware (T021) is responsible for identity verification and
for populating the ``AuthenticatedUser`` context.  ABAC (attribute-based access
control) — such as cross-application scope enforcement — is implemented in the
Identity bounded context (T030, T031) using the types defined here.

Dependency rule: this module imports only from the Python standard library and
from ``mil.kernel.types`` and ``mil.kernel.errors``.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mil.kernel.errors import AuthorizationError

if TYPE_CHECKING:
    from mil.kernel.types import TenantId, UserId

# ---------------------------------------------------------------------------
# Role constants
# ---------------------------------------------------------------------------


class Role:
    """
    RBAC roles assigned to platform users.

    Each role corresponds to a distinct professional function in the mortgage
    review workflow.  A user may hold multiple roles.
    """

    VERIFICATION_OFFICER = "VERIFICATION_OFFICER"
    UNDERWRITER = "UNDERWRITER"
    CREDIT_ANALYST = "CREDIT_ANALYST"
    RISK_ANALYST = "RISK_ANALYST"
    COMPLIANCE_OFFICER = "COMPLIANCE_OFFICER"
    AUDIT_TEAM = "AUDIT_TEAM"
    OPERATIONS_MANAGER = "OPERATIONS_MANAGER"
    RELATIONSHIP_MANAGER = "RELATIONSHIP_MANAGER"
    ADMIN = "ADMIN"
    SERVICE_ACCOUNT = "SERVICE_ACCOUNT"
    # spec 005-enterprise-platform §4 (Policy Administration, Wave 1): drafts
    # and submits Policy Packs for approval, but cannot approve/activate its
    # own submissions (maker-checker; that authority stays with
    # COMPLIANCE_OFFICER/ADMIN via MANAGE_POLICY_PACKS).
    POLICY_ADMINISTRATOR = "POLICY_ADMINISTRATOR"
    # spec 005-enterprise-platform §12 (Customer Portal, Wave 4): a minimal,
    # internal-only synthetic role constructed exclusively by
    # ``PortalWorkspace`` (mil.api.deps) to satisfy ``DocumentService.
    # ingest_document``'s existing RBAC check when a borrower uploads
    # through the reused upload contract (FR-CP-003: no separate upload
    # pipeline). Never assignable to a real user, never surfaced through
    # any admin UI, never granted more than the one permission below —
    # deliberately not "internal RBAC extended to borrowers," but the
    # narrowest possible reuse of an already-built permission gate.
    PORTAL_ACCOUNT = "PORTAL_ACCOUNT"


# ---------------------------------------------------------------------------
# Permission constants
# ---------------------------------------------------------------------------


class Permission:
    """
    Granular permission constants for access control checks.

    Permissions follow the ``action:resource`` convention.  Service-layer code
    calls ``require_permission(user, Permission.XYZ)`` rather than comparing
    role strings directly, which allows the RBAC mapping to evolve without
    touching business logic.
    """

    # Application & Party
    READ_APPLICATION = "read:application"
    WRITE_APPLICATION = "write:application"
    READ_PARTY = "read:party"
    WRITE_PARTY = "write:party"

    # Document
    READ_DOCUMENT = "read:document"
    UPLOAD_DOCUMENT = "upload:document"

    # Evidence
    READ_EVIDENCE = "read:evidence"

    # Findings
    READ_FINDINGS = "read:findings"
    VERIFY_FINDING = "verify:finding"
    OVERRIDE_FINDING = "override:finding"
    ESCALATE_FINDING = "escalate:finding"

    # Copilot
    QUERY_COPILOT = "query:copilot"

    # Collaboration (spec 005-enterprise-platform §9) — comments on a
    # Finding's Review Session. Granted to every role that holds
    # READ_FINDINGS: discussion is not a decision (Principle I only
    # restricts decision authority, not commentary), so read-only observer
    # roles (Compliance/Risk/Audit) may still ask questions/flag concerns.
    COMMENT_ON_FINDING = "comment:finding"

    # Operational Intelligence
    READ_OPERATIONAL = "read:operational"

    # Audit
    READ_AUDIT = "read:audit"

    # Integration
    MANAGE_INTEGRATION = "manage:integration"
    # spec 005-enterprise-platform §2 (Wave 2): narrower than
    # MANAGE_INTEGRATION (connection admin) — pushing a readiness
    # notification to the LOS is a routine human review action.
    PUSH_LOS_STATUS = "push:los_status"

    # Identity & administration
    MANAGE_USERS = "manage:users"
    MANAGE_ROLES = "manage:roles"
    MANAGE_POLICY_PACKS = "manage:policy_packs"
    # spec 005-enterprise-platform §4: narrower than MANAGE_POLICY_PACKS —
    # draft/submit only, no approve/activate authority.
    DRAFT_POLICY_PACK = "draft:policy_pack"
    READ_POLICY_RESULTS = "read:policy_results"

    # Assignment (spec 005-enterprise-platform §1, Wave 2 — RM/Banker Workspace)
    MANAGE_ASSIGNMENT = "manage:assignment"

    # Borrower Identity Resolution / Cross-Application Intelligence
    # (spec 005-enterprise-platform §5/§6, Wave 3) — the explicit, audited
    # exception to ABAC's default cross-application denial (abac.py).
    READ_CROSS_APPLICATION_IDENTITY = "read:cross_application_identity"
    CONFIRM_IDENTITY_MATCH = "confirm:identity_match"

    # Business Analytics (spec 005-enterprise-platform §11, Wave 3)
    READ_ANALYTICS = "read:analytics"

    # Customer Portal (spec 005-enterprise-platform §12, Wave 4) — internal-
    # staff-side checklist management only; portal accounts themselves are
    # never evaluated through this permission system at all.
    MANAGE_CHECKLIST = "manage:checklist"

    # Security & Compliance (spec 005-enterprise-platform §16, Wave 4)
    MANAGE_COMPLIANCE = "manage:compliance"
    READ_COMPLIANCE = "read:compliance"

    # Super-permission (only ADMIN role)
    ADMIN = "admin"


# ---------------------------------------------------------------------------
# Role → Permission mapping
# ---------------------------------------------------------------------------

#: Default RBAC permission map.  Each role is mapped to a frozenset of the
#: permissions it grants.  ADMIN role receives the ``Permission.ADMIN``
#: super-permission, which is checked separately in ``has_permission``.
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    Role.RELATIONSHIP_MANAGER: frozenset(
        {
            Permission.READ_APPLICATION,
            Permission.WRITE_APPLICATION,
            Permission.READ_PARTY,
            Permission.WRITE_PARTY,
            Permission.READ_DOCUMENT,
            Permission.UPLOAD_DOCUMENT,
            Permission.READ_FINDINGS,
            Permission.COMMENT_ON_FINDING,
            Permission.MANAGE_ASSIGNMENT,
            Permission.PUSH_LOS_STATUS,
            # RM sees the Borrower Profile (read) but does not confirm
            # identity merges — that authority stays with Underwriter/Risk/
            # Compliance, matching the "advisory, human-reviewable" model.
            Permission.READ_CROSS_APPLICATION_IDENTITY,
            Permission.MANAGE_CHECKLIST,
        }
    ),
    Role.VERIFICATION_OFFICER: frozenset(
        {
            Permission.READ_APPLICATION,
            Permission.READ_PARTY,
            Permission.READ_DOCUMENT,
            Permission.READ_EVIDENCE,
            Permission.READ_FINDINGS,
            Permission.VERIFY_FINDING,
            Permission.OVERRIDE_FINDING,
            Permission.ESCALATE_FINDING,
            Permission.QUERY_COPILOT,
            Permission.COMMENT_ON_FINDING,
        }
    ),
    Role.CREDIT_ANALYST: frozenset(
        {
            Permission.READ_APPLICATION,
            Permission.READ_PARTY,
            Permission.READ_DOCUMENT,
            Permission.READ_EVIDENCE,
            Permission.READ_FINDINGS,
            Permission.READ_POLICY_RESULTS,
            Permission.QUERY_COPILOT,
            Permission.COMMENT_ON_FINDING,
        }
    ),
    Role.UNDERWRITER: frozenset(
        {
            Permission.READ_APPLICATION,
            Permission.READ_PARTY,
            Permission.READ_DOCUMENT,
            Permission.READ_EVIDENCE,
            Permission.READ_FINDINGS,
            Permission.READ_POLICY_RESULTS,
            Permission.VERIFY_FINDING,
            Permission.OVERRIDE_FINDING,
            Permission.ESCALATE_FINDING,
            Permission.QUERY_COPILOT,
            Permission.COMMENT_ON_FINDING,
            Permission.MANAGE_ASSIGNMENT,
            Permission.PUSH_LOS_STATUS,
            Permission.READ_CROSS_APPLICATION_IDENTITY,
            Permission.CONFIRM_IDENTITY_MATCH,
            Permission.MANAGE_CHECKLIST,
        }
    ),
    Role.RISK_ANALYST: frozenset(
        {
            Permission.READ_APPLICATION,
            Permission.READ_EVIDENCE,
            Permission.READ_FINDINGS,
            Permission.READ_POLICY_RESULTS,
            Permission.READ_OPERATIONAL,
            Permission.COMMENT_ON_FINDING,
            Permission.READ_CROSS_APPLICATION_IDENTITY,
            Permission.CONFIRM_IDENTITY_MATCH,
        }
    ),
    Role.COMPLIANCE_OFFICER: frozenset(
        {
            Permission.READ_APPLICATION,
            Permission.READ_EVIDENCE,
            Permission.READ_FINDINGS,
            Permission.READ_POLICY_RESULTS,
            Permission.READ_AUDIT,
            Permission.READ_OPERATIONAL,
            # spec 005-enterprise-platform §4: Compliance holds approval
            # authority (maker-checker's "checker" role) over Policy Packs.
            Permission.MANAGE_POLICY_PACKS,
            Permission.COMMENT_ON_FINDING,
            Permission.READ_CROSS_APPLICATION_IDENTITY,
            Permission.CONFIRM_IDENTITY_MATCH,
            Permission.READ_ANALYTICS,
            Permission.MANAGE_COMPLIANCE,
        }
    ),
    Role.AUDIT_TEAM: frozenset(
        {
            Permission.READ_APPLICATION,
            Permission.READ_PARTY,
            Permission.READ_DOCUMENT,
            Permission.READ_EVIDENCE,
            Permission.READ_FINDINGS,
            Permission.READ_POLICY_RESULTS,
            Permission.READ_AUDIT,
            Permission.COMMENT_ON_FINDING,
            # spec 005-enterprise-platform §16: the audit function reviews
            # compliance reports, it doesn't configure retention policy
            # (that stays MANAGE_COMPLIANCE, Compliance Officer/Admin only).
            Permission.READ_COMPLIANCE,
        }
    ),
    Role.OPERATIONS_MANAGER: frozenset(
        {
            Permission.READ_APPLICATION,
            Permission.READ_OPERATIONAL,
            Permission.READ_AUDIT,
            Permission.READ_ANALYTICS,
        }
    ),
    Role.POLICY_ADMINISTRATOR: frozenset(
        {
            Permission.DRAFT_POLICY_PACK,
            Permission.READ_POLICY_RESULTS,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Permission.ADMIN,
            Permission.MANAGE_USERS,
            Permission.MANAGE_ROLES,
            Permission.MANAGE_POLICY_PACKS,
            Permission.DRAFT_POLICY_PACK,
            Permission.READ_POLICY_RESULTS,
            Permission.MANAGE_INTEGRATION,
        }
    ),
    Role.SERVICE_ACCOUNT: frozenset(
        {
            Permission.READ_APPLICATION,
            Permission.READ_DOCUMENT,
            Permission.MANAGE_INTEGRATION,
        }
    ),
    Role.PORTAL_ACCOUNT: frozenset({Permission.UPLOAD_DOCUMENT}),
}


# ---------------------------------------------------------------------------
# Authenticated principal context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthenticatedUser:
    """
    The immutable security context for an authenticated request principal.

    This object is created by the Zero Trust authentication middleware (T021)
    after verifying the identity token.  It is stored in a context variable and
    accessed by service-layer code via ``current_user()``.

    Attributes:
        user_id: Unique identifier of the authenticated user.
        tenant_id: Tenant to which this user belongs.  All data access is
                   scoped to this tenant by default.
        roles: The set of RBAC roles held by this user.  An empty set means
               the user is authenticated but has no permissions.
        email: User's email address (for audit event enrichment).
        display_name: Human-readable name used in audit trails and UI.
    """

    user_id: UserId
    tenant_id: TenantId
    roles: frozenset[str] = field(default_factory=frozenset)
    email: str = ""
    display_name: str = ""


# ---------------------------------------------------------------------------
# Request context variable
# ---------------------------------------------------------------------------

_current_user_var: contextvars.ContextVar[AuthenticatedUser | None] = contextvars.ContextVar(
    "current_user",
    default=None,
)


def set_current_user(user: AuthenticatedUser) -> contextvars.Token[AuthenticatedUser | None]:
    """
    Bind ``user`` as the current authenticated principal for this request context.

    Called by the authentication middleware after token verification.  Returns
    a token that can be passed to ``_current_user_var.reset()`` to restore the
    previous context (useful in tests).
    """
    return _current_user_var.set(user)


def current_user() -> AuthenticatedUser | None:
    """
    Return the authenticated principal for the current request context.

    Returns ``None`` if called outside a request context or before the
    authentication middleware has run.
    """
    return _current_user_var.get()


# ---------------------------------------------------------------------------
# RBAC helper functions
# ---------------------------------------------------------------------------


def has_role(user: AuthenticatedUser, role: str) -> bool:
    """Return ``True`` if the user holds the specified role."""
    return role in user.roles


def has_permission(user: AuthenticatedUser, permission: str) -> bool:
    """
    Return ``True`` if the user's roles grant the specified permission.

    A user with the ``Permission.ADMIN`` super-permission (via the ``ADMIN``
    role) is granted access to all permissions.
    """
    granted: set[str] = set()
    for role in user.roles:
        granted.update(ROLE_PERMISSIONS.get(role, frozenset()))

    if Permission.ADMIN in granted:
        return True

    return permission in granted


def require_permission(user: AuthenticatedUser, permission: str) -> None:
    """
    Raise ``AuthorizationError`` if the user does not have ``permission``.

    Service-layer code calls this at the start of any operation that requires
    a specific permission, providing a consistent authorisation pattern across
    all bounded contexts::

        def verify_finding(user: AuthenticatedUser, finding_id: FindingId) -> None:
            require_permission(user, Permission.VERIFY_FINDING)
            ...

    Raises:
        AuthorizationError: When the user's roles do not grant the required
            permission.
    """
    if not has_permission(user, permission):
        raise AuthorizationError(
            message=f"Permission denied: '{permission}' is required",
            required_permission=permission,
        )
