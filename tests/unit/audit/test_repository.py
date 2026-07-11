"""Unit tests for mil.audit.repository — AuditRepository."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from mil.audit.repository import AuditRepository


def _make_repository() -> tuple[AuditRepository, MagicMock]:
    session = MagicMock()
    return AuditRepository(session), session


class TestGetForApplication:
    def test_queries_scalars_and_returns_list(self) -> None:
        repo, session = _make_repository()
        fake_event = object()
        session.scalars.return_value = [fake_event]

        result = repo.get_for_application(uuid4())

        assert result == [fake_event]
        session.scalars.assert_called_once()

    def test_empty_result_returns_empty_list(self) -> None:
        repo, session = _make_repository()
        session.scalars.return_value = []

        result = repo.get_for_application(uuid4())

        assert result == []


class TestGetForApplicationInRange:
    def test_queries_scalars_and_returns_list(self) -> None:
        from datetime import UTC, datetime

        repo, session = _make_repository()
        fake_event = object()
        session.scalars.return_value = [fake_event]

        result = repo.get_for_application_in_range(
            uuid4(), from_date=datetime(2026, 1, 1, tzinfo=UTC), to_date=datetime(2026, 2, 1, tzinfo=UTC)
        )

        assert result == [fake_event]
        session.scalars.assert_called_once()

    def test_empty_result_returns_empty_list(self) -> None:
        from datetime import UTC, datetime

        repo, session = _make_repository()
        session.scalars.return_value = []

        result = repo.get_for_application_in_range(
            uuid4(), from_date=datetime(2026, 1, 1, tzinfo=UTC), to_date=datetime(2026, 2, 1, tzinfo=UTC)
        )

        assert result == []
