"""Unit tests for mil.assignment.service — AssignmentService."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.assignment.models import Assignment, AssignmentHistory
from mil.assignment.service import AssignmentService
from mil.kernel.errors import AuthorizationError
from mil.kernel.security import AuthenticatedUser, Role


class FakeAssignmentRepository:
    def __init__(self) -> None:
        self.by_application: dict[object, Assignment] = {}
        self.history: list[AssignmentHistory] = []

    def save(self, assignment: Assignment) -> None:
        self.by_application[assignment.application_id] = assignment

    def save_history(self, entry: AssignmentHistory) -> None:
        self.history.append(entry)

    def get_for_application(self, application_id: object) -> Assignment | None:
        return self.by_application.get(application_id)

    def get_history_for_application(self, application_id: object) -> list[AssignmentHistory]:
        return [h for h in self.history if h.application_id == application_id]

    def get_owned_by(self, owner_user_id: object) -> list[Assignment]:
        return [a for a in self.by_application.values() if a.owner_user_id == owner_user_id]

    def get_reviewed_by(self, reviewer_user_id: object) -> list[Assignment]:
        return [a for a in self.by_application.values() if a.reviewer_user_id == reviewer_user_id]


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return object()


def _make_service() -> tuple[AssignmentService, FakeAssignmentRepository, FakeAuditWriter]:
    repo = FakeAssignmentRepository()
    audit = FakeAuditWriter()
    return AssignmentService(repo, audit), repo, audit  # type: ignore[arg-type]


def _rm_caller(tenant_id: object, user_id: object | None = None) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id or uuid4(), tenant_id=tenant_id, roles=frozenset({Role.RELATIONSHIP_MANAGER})
    )


def _readonly_caller(tenant_id: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid4(), tenant_id=tenant_id, roles=frozenset({Role.AUDIT_TEAM})
    )


class TestSetAssignment:
    def test_creates_new_assignment(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _rm_caller(tenant_id)
        app_id = uuid4()
        owner = uuid4()

        assignment = service.set_assignment(
            caller, application_id=app_id, tenant_id=tenant_id, owner_user_id=owner
        )

        assert assignment.owner_user_id == owner
        assert audit.records[-1]["event_type"] == "ASSIGNMENT_CREATED"
        assert len(repo.history) == 0

    def test_reassignment_snapshots_history(self) -> None:
        service, repo, audit = _make_service()
        tenant_id = uuid4()
        caller = _rm_caller(tenant_id)
        app_id = uuid4()
        first_owner = uuid4()
        second_owner = uuid4()

        service.set_assignment(
            caller, application_id=app_id, tenant_id=tenant_id, owner_user_id=first_owner
        )
        updated = service.set_assignment(
            caller, application_id=app_id, tenant_id=tenant_id, owner_user_id=second_owner
        )

        assert updated.owner_user_id == second_owner
        assert len(repo.history) == 1
        assert repo.history[0].owner_user_id == first_owner
        assert audit.records[-1]["event_type"] == "ASSIGNMENT_UPDATED"

    def test_readonly_role_forbidden(self) -> None:
        service, _, _ = _make_service()
        caller = _readonly_caller(uuid4())
        with pytest.raises(AuthorizationError):
            service.set_assignment(
                caller, application_id=uuid4(), tenant_id=uuid4(), owner_user_id=uuid4()
            )


class TestGetPortfolio:
    def test_returns_only_callers_own_applications(self) -> None:
        service, repo, _ = _make_service()
        tenant_id = uuid4()
        owner_id = uuid4()
        caller = _rm_caller(tenant_id, owner_id)

        service.set_assignment(
            caller, application_id=uuid4(), tenant_id=tenant_id, owner_user_id=owner_id
        )
        other_caller = _rm_caller(tenant_id)
        service.set_assignment(
            other_caller, application_id=uuid4(), tenant_id=tenant_id, owner_user_id=other_caller.user_id
        )

        portfolio = service.get_portfolio(caller)
        assert len(portfolio) == 1
        assert portfolio[0].owner_user_id == owner_id
