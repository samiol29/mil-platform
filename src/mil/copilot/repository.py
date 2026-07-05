"""
Persistence gateway for the Copilot bounded context foundation.

``CopilotRepository`` covers all three Copilot entities. Every write is
append-only: there is no update or delete method anywhere in this module.

- ``create_session`` — a session is created once and never mutated.
- ``append_query`` / ``append_response`` — immutable rows, added and never
  updated (a response can never overwrite a prior one; ``query_id`` is
  unique at the database level).

None of these methods commit — the caller's Unit of Work owns the
transaction, matching the platform-wide per-job/per-request commit discipline
(ADR-008).

Dependency rule: imports only from ``mil.copilot.models``, ``mil.kernel``, and
the Python standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from mil.copilot.models import CopilotQuery, CopilotResponse, CopilotSession

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class CopilotRepository:
    """Persistence gateway for ``CopilotSession``, ``CopilotQuery``, and ``CopilotResponse`` rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # CopilotSession (append-only)
    # ------------------------------------------------------------------

    def create_session(self, copilot_session: CopilotSession) -> None:
        """Persist a new Copilot Session. Adds and flushes."""
        self._session.add(copilot_session)
        self._session.flush()

    def get_session(self, session_id: UUID) -> CopilotSession | None:
        """Return the Copilot Session with the given id, or ``None``."""
        return self._session.get(CopilotSession, session_id)

    def get_latest_session_for_application(self, application_id: UUID) -> CopilotSession | None:
        """Return the most recently created Copilot Session for an application, or ``None``."""
        stmt = (
            select(CopilotSession)
            .where(CopilotSession.application_id == application_id)
            .order_by(CopilotSession.created_at.desc())
        )
        return self._session.scalars(stmt).first()

    # ------------------------------------------------------------------
    # CopilotQuery (append-only)
    # ------------------------------------------------------------------

    def append_query(self, query: CopilotQuery) -> None:
        """Persist an immutable query record. Adds and flushes."""
        self._session.add(query)
        self._session.flush()

    def get_queries_for_session(self, session_id: UUID) -> list[CopilotQuery]:
        """Return every query on a Copilot Session, oldest first."""
        stmt = (
            select(CopilotQuery)
            .where(CopilotQuery.session_id == session_id)
            .order_by(CopilotQuery.created_at.asc())
        )
        return list(self._session.scalars(stmt))

    # ------------------------------------------------------------------
    # CopilotResponse (append-only)
    # ------------------------------------------------------------------

    def append_response(self, response: CopilotResponse) -> None:
        """Persist an immutable response record. Adds and flushes. Never overwrites."""
        self._session.add(response)
        self._session.flush()

    def get_history(self, session_id: UUID) -> list[tuple[CopilotQuery, CopilotResponse | None]]:
        """
        Return the full, ordered query/response history for a session.

        Each query is paired with its response, or ``None`` if a response has
        not yet been recorded for that query.
        """
        queries = self.get_queries_for_session(session_id)
        if not queries:
            return []
        query_ids = [query.id for query in queries]
        stmt = select(CopilotResponse).where(CopilotResponse.query_id.in_(query_ids))
        responses_by_query_id = {
            response.query_id: response for response in self._session.scalars(stmt)
        }
        return [(query, responses_by_query_id.get(query.id)) for query in queries]
