"""
ORM models for the Copilot bounded context foundation (US2 Sprint 7A).

Three entities, all append-only:

- ``CopilotSession`` — the container for one reviewer's Copilot interaction
  with a single application. Application-scoped and tenant-aware. Created
  once by ``CopilotService.create_session`` and never mutated afterwards —
  Sprint 7A defines no session lifecycle (close/reopen) because no
  conversation memory or multi-turn state is implemented yet.
- ``CopilotQuery`` — one immutable, append-only record of a human reviewer's
  natural-language question, belonging to a session.
- ``CopilotResponse`` — one immutable, append-only record of the answer to a
  query, carrying the versioned attribution (``prompt_version``,
  ``model_version``) Engineering Constitution Principle XII requires and the
  citations (``mil.copilot.citations.Citation``) that ground it. A response
  is never overwritten; ``query_id`` is unique so at most one response is
  ever recorded per query (regeneration is out of scope for Sprint 7A).

No row in this module is ever produced by calling an ``InferenceProvider`` —
Sprint 7A persists only what a caller supplies. Inference, prompt execution,
and citation-against-grounding validation are Sprint 7B concerns.

Dependency rule: imports only from ``mil.kernel``, ``mil.copilot.citations``,
and the Python standard library.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base
from mil.kernel.errors import ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from mil.copilot.citations import Citation


class CopilotSession(Base):
    """
    A reviewer's Copilot interaction session, scoped to one application.

    Created once, at the start of an interaction. Sprint 7A records no
    further state on the session itself — queries and responses are appended
    as separate, immutable rows referencing it.
    """

    __tablename__ = "copilot_sessions"
    __table_args__ = ({"schema": "copilot"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("core.applications.id"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def create(
        cls,
        *,
        application_id: UUID,
        tenant_id: UUID,
        created_by_user_id: UUID,
        correlation_id: str,
    ) -> CopilotSession:
        """Create a new Copilot Session for a human reviewer on one application."""
        if not correlation_id:
            raise ValidationError("correlation_id must not be empty", field="correlation_id")
        return cls(
            id=uuid4(),
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=created_by_user_id,
            correlation_id=correlation_id,
            created_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return f"<CopilotSession id={self.id} application={self.application_id}>"


class CopilotQuery(Base):
    """
    Immutable, append-only record of one natural-language question.

    Always attributed to an authenticated human reviewer — the Copilot never
    originates its own queries.
    """

    __tablename__ = "copilot_queries"
    __table_args__ = ({"schema": "copilot"},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("copilot.copilot_sessions.id"), nullable=False
    )
    asked_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def create(
        cls, *, session_id: UUID, asked_by_user_id: UUID, question_text: str
    ) -> CopilotQuery:
        """Create an immutable query record."""
        if not question_text or not question_text.strip():
            raise ValidationError("question_text must not be empty", field="question_text")
        return cls(
            id=uuid4(),
            session_id=session_id,
            asked_by_user_id=asked_by_user_id,
            question_text=question_text,
            created_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return f"<CopilotQuery id={self.id} session={self.session_id}>"


class CopilotResponse(Base):
    """
    Immutable, append-only record of the answer to a query.

    Carries the versioned attribution Principle XII requires
    (``prompt_version``, ``model_version``) and the citations grounding the
    answer. ``query_id`` is unique: a response is never overwritten, and at
    most one is ever recorded per query.
    """

    __tablename__ = "copilot_responses"
    __table_args__ = (
        UniqueConstraint("query_id", name="uq_copilot_responses_query_id"),
        {"schema": "copilot"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    query_id: Mapped[UUID] = mapped_column(ForeignKey("copilot.copilot_queries.id"), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    citations: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def create(
        cls,
        *,
        query_id: UUID,
        answer_text: str,
        prompt_version: str,
        model_version: str,
        citations: Sequence[Citation] = (),
    ) -> CopilotResponse:
        """
        Create an immutable response record.

        Raises:
            ValidationError: If ``answer_text``, ``prompt_version``, or
                ``model_version`` is empty. All three are required for
                Principle III explainability and Principle XII attribution.
        """
        if not answer_text or not answer_text.strip():
            raise ValidationError("answer_text must not be empty", field="answer_text")
        if not prompt_version:
            raise ValidationError("prompt_version must not be empty", field="prompt_version")
        if not model_version:
            raise ValidationError("model_version must not be empty", field="model_version")
        return cls(
            id=uuid4(),
            query_id=query_id,
            answer_text=answer_text,
            prompt_version=prompt_version,
            model_version=model_version,
            citations=[citation.to_dict() for citation in citations],
            created_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return f"<CopilotResponse id={self.id} query={self.query_id}>"
