"""
AssignmentService — use-case orchestrator for the Assignment bounded context
(spec 005-enterprise-platform §1, Wave 2).

Every method takes ``caller`` and self-checks ``manage:assignment``,
matching the convention established by `IdentityService`/`PolicyService`'s
new methods in Wave 1.

Dependency rule: imports only from ``mil.assignment``, ``mil.kernel``, and
the Python standard library. No other bounded context is imported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.assignment.models import Assignment, AssignmentHistory
from mil.kernel.security import Permission, require_permission

if TYPE_CHECKING:
    from uuid import UUID

    from mil.assignment.repository import AssignmentRepository
    from mil.audit.writer import AuditWriter
    from mil.kernel.security import AuthenticatedUser


class AssignmentService:
    def __init__(self, repository: AssignmentRepository, audit: AuditWriter) -> None:
        self._repo = repository
        self._audit = audit

    def get_assignment(self, caller: AuthenticatedUser, application_id: UUID) -> Assignment | None:
        require_permission(caller, Permission.MANAGE_ASSIGNMENT)
        return self._repo.get_for_application(application_id)

    def get_history(
        self, caller: AuthenticatedUser, application_id: UUID
    ) -> list[AssignmentHistory]:
        require_permission(caller, Permission.MANAGE_ASSIGNMENT)
        return self._repo.get_history_for_application(application_id)

    def set_assignment(
        self,
        caller: AuthenticatedUser,
        *,
        application_id: UUID,
        tenant_id: UUID,
        owner_user_id: UUID,
        reviewer_user_id: UUID | None = None,
    ) -> Assignment:
        """
        Create or update the assignment for an application.

        A reassignment first snapshots the existing row into
        ``AssignmentHistory`` (append-only), then updates the live row in
        place — never overwritten silently.
        """
        require_permission(caller, Permission.MANAGE_ASSIGNMENT)
        existing = self._repo.get_for_application(application_id)
        if existing is None:
            assignment = Assignment.create(
                application_id=application_id,
                owner_user_id=owner_user_id,
                assigned_by_user_id=caller.user_id,
                reviewer_user_id=reviewer_user_id,
            )
            self._repo.save(assignment)
            event_type = "ASSIGNMENT_CREATED"
        else:
            self._repo.save_history(AssignmentHistory.snapshot(existing))
            existing.reassign(
                owner_user_id=owner_user_id,
                reviewer_user_id=reviewer_user_id,
                assigned_by_user_id=caller.user_id,
            )
            self._repo.save(existing)
            assignment = existing
            event_type = "ASSIGNMENT_UPDATED"

        self._audit.record(
            event_type=event_type,
            entity_type="ASSIGNMENT",
            entity_id=assignment.id,
            tenant_id=tenant_id,
            application_id=application_id,
            actor_id=caller.user_id,
            event_data={
                "owner_user_id": str(assignment.owner_user_id),
                "reviewer_user_id": (
                    str(assignment.reviewer_user_id)
                    if assignment.reviewer_user_id is not None
                    else None
                ),
            },
        )
        return assignment

    def get_portfolio(self, caller: AuthenticatedUser) -> list[Assignment]:
        """Applications the caller owns (RM's own portfolio)."""
        require_permission(caller, Permission.MANAGE_ASSIGNMENT)
        return self._repo.get_owned_by(caller.user_id)
