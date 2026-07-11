"""Unit tests for mil.assignment.models — Assignment/AssignmentHistory."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.assignment.models import Assignment, AssignmentHistory
from mil.kernel.errors import ValidationError


class TestAssignmentCreate:
    def test_create_sets_owner(self) -> None:
        app_id, owner, assigner = uuid4(), uuid4(), uuid4()
        assignment = Assignment.create(
            application_id=app_id, owner_user_id=owner, assigned_by_user_id=assigner
        )
        assert assignment.owner_user_id == owner
        assert assignment.reviewer_user_id is None


class TestAssignmentReassign:
    def test_reassign_updates_reviewer(self) -> None:
        assignment = Assignment.create(
            application_id=uuid4(), owner_user_id=uuid4(), assigned_by_user_id=uuid4()
        )
        reviewer = uuid4()
        assigner = uuid4()
        assignment.reassign(reviewer_user_id=reviewer, assigned_by_user_id=assigner)
        assert assignment.reviewer_user_id == reviewer
        assert assignment.assigned_by_user_id == assigner

    def test_reassign_requires_at_least_one_field(self) -> None:
        assignment = Assignment.create(
            application_id=uuid4(), owner_user_id=uuid4(), assigned_by_user_id=uuid4()
        )
        with pytest.raises(ValidationError):
            assignment.reassign(assigned_by_user_id=uuid4())


class TestAssignmentHistorySnapshot:
    def test_snapshot_copies_current_state(self) -> None:
        assignment = Assignment.create(
            application_id=uuid4(), owner_user_id=uuid4(), assigned_by_user_id=uuid4()
        )
        snapshot = AssignmentHistory.snapshot(assignment)
        assert snapshot.application_id == assignment.application_id
        assert snapshot.owner_user_id == assignment.owner_user_id
        assert snapshot.id != assignment.id
