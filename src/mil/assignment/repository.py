"""Persistence gateway for the Assignment bounded context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from mil.assignment.models import Assignment, AssignmentHistory

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class AssignmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, assignment: Assignment) -> None:
        self._session.add(assignment)
        self._session.flush()

    def save_history(self, entry: AssignmentHistory) -> None:
        self._session.add(entry)
        self._session.flush()

    def get_for_application(self, application_id: UUID) -> Assignment | None:
        stmt = select(Assignment).where(Assignment.application_id == application_id)
        return self._session.scalars(stmt).one_or_none()

    def get_history_for_application(self, application_id: UUID) -> list[AssignmentHistory]:
        stmt = (
            select(AssignmentHistory)
            .where(AssignmentHistory.application_id == application_id)
            .order_by(AssignmentHistory.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def get_owned_by(self, owner_user_id: UUID) -> list[Assignment]:
        stmt = select(Assignment).where(Assignment.owner_user_id == owner_user_id)
        return list(self._session.scalars(stmt))

    def get_reviewed_by(self, reviewer_user_id: UUID) -> list[Assignment]:
        stmt = select(Assignment).where(Assignment.reviewer_user_id == reviewer_user_id)
        return list(self._session.scalars(stmt))
