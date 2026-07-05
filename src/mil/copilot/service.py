"""
CopilotService — use-case orchestrator for the Copilot bounded context
(US2 Sprint 7A foundation + Sprint 7B inference + Sprint 7C API integration).

Responsibilities:

- ``create_session`` / ``start_or_resume_session`` / ``submit_query`` /
  ``record_response`` — create and append the three Copilot entities, each
  recorded in the same transaction as its audit event (audit is synchronous
  and never routed through the outbox — ADR-007).
- ``get_session`` / ``get_latest_session_for_application`` / ``get_history``
  (Sprint 7C) — read-only session/history retrieval for the REST API,
  enforcing tenant isolation and recording a synchronous
  ``COPILOT_RESPONSE_VIEWED`` audit event whenever a previously generated
  response is retrieved.
- ``assemble_grounding`` — build an application-scoped, read-only
  ``GroundingBundle`` by calling the Query Ports introduced during
  architecture preparation (ADR-010): ``ApplicationReader``,
  ``DocumentReader``, ``EvidenceReader``, ``FindingReader``,
  ``PolicyResultReader``, ``ReviewReader``. This service depends only on
  those port abstractions — it never imports ``mil.application``,
  ``mil.document``, ``mil.evidence``, ``mil.finding``, ``mil.policy``, or
  ``mil.review`` internals (ADR-010: consumer-owned interfaces, adapters
  wired only in the composition root, not here).
- ``generate_response`` (Sprint 7B; prompt selection updated in Sprint 7C) —
  classifies the query into a prompt identifier via the deterministic,
  rule-based ``mil.copilot.classifier`` (no AI), assembles grounding,
  transforms it into the generalized, domain-agnostic ``InferenceContext``
  (``GroundingItem``, ADR-011 §3 generalized inference architecture),
  resolves the pinned prompt version from the Prompt Registry, calls the
  injected ``InferenceProvider``, validates every returned citation against
  the grounding set, and persists the result. If grounding is absent or the
  model's answer cannot be grounded in a citation, this returns a safe,
  explicit "insufficient grounding" response instead of ever surfacing an
  unfounded claim (Principle III; ADR-011 §6 hallucination policy).

Authorization (Sprint 7C): every public entry point reachable from an HTTP
endpoint requires an ``AuthenticatedUser`` and calls
``require_permission(user, Permission.QUERY_COPILOT)`` as its first action —
identical to how every other bounded-context service enforces RBAC
(``mil.kernel.security``). Routes never check permissions themselves.

``CopilotService`` never mutates any record read through a Query Port. The
``InferenceProvider`` is injected already resolved — the composition root
that constructs this service must resolve it exclusively via
``ProviderRegistry.get_inference()``; concrete provider classes are never
imported here (ARCHITECTURE.md §5/§6).

Dependency rule: imports only from ``mil.copilot``, ``mil.kernel``, and the
Python standard library. No other bounded context is imported.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from mil.copilot.citations import (
    APPLICATION,
    DOCUMENT,
    DOCUMENT_TEXT,
    EVIDENCE,
    FINDING,
    POLICY_RESULT,
    REVIEW_ACTION,
    Citation,
)
from mil.copilot.classifier import classify_query
from mil.copilot.models import CopilotQuery, CopilotResponse, CopilotSession
from mil.copilot.prompts import get_prompt_version
from mil.kernel.errors import (
    NotFoundError,
    ProviderError,
    ProviderVersionMissingError,
    ScopeViolationError,
)
from mil.kernel.providers.inference import GroundingItem, InferenceContext
from mil.kernel.security import Permission, require_permission

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from mil.audit.writer import AuditWriter
    from mil.copilot.ports import (
        ApplicationReader,
        ApplicationView,
        DocumentReader,
        DocumentTextReader,
        DocumentTextView,
        DocumentView,
        EvidenceReader,
        EvidenceView,
        FindingReader,
        FindingView,
        PolicyResultReader,
        PolicyResultView,
        ReviewActionView,
        ReviewReader,
        ReviewSessionView,
    )
    from mil.copilot.repository import CopilotRepository
    from mil.kernel.providers.inference import InferenceProvider
    from mil.kernel.security import AuthenticatedUser

# ---------------------------------------------------------------------------
# Hallucination policy: the fixed, deterministic refusal message.
#
# This is not a claim about mortgage data — it is a meta-statement that no
# governed grounding was available or citable. It carries no citations
# because it asserts nothing about the application; it is a safe failure,
# not an ungrounded answer (ADR-011 §6).
# ---------------------------------------------------------------------------

# Principle V (least-data): a document's full transcribed text can be long;
# cap what is sent to the model per document rather than passing arbitrarily
# large content. Chosen generously (~1000 words) since raw text is the primary
# grounding source for free-form "summarize this document" style questions.
_DOCUMENT_TEXT_SUMMARY_LIMIT = 6000

_INSUFFICIENT_GROUNDING_MESSAGE = (
    "I don't have enough governed evidence, findings, policy results, or review "
    "history recorded for this application yet to answer that question. Please "
    "check back once more data has been processed, or consult a reviewer directly."
)


@dataclasses.dataclass(frozen=True)
class GroundingBundle:
    """
    An application-scoped, read-only bundle of governed records.

    Assembled by ``CopilotService.assemble_grounding`` exclusively through
    Query Ports (ADR-010) — nothing in this bundle is fetched by importing
    another bounded context's repository or service directly.
    """

    application_id: UUID
    application: ApplicationView
    documents: tuple[DocumentView, ...]
    evidence: tuple[EvidenceView, ...]
    findings: tuple[FindingView, ...]
    policy_results: tuple[PolicyResultView, ...]
    review_sessions: tuple[ReviewSessionView, ...]
    review_actions: tuple[ReviewActionView, ...] = ()
    document_texts: tuple[DocumentTextView, ...] = ()


class CopilotService:
    """
    Orchestrates Copilot session/query/response bookkeeping, read-only
    grounding assembly, and grounded response generation.

    Construct per unit of work with a repository, audit writer, the injected
    ``InferenceProvider`` (already resolved via ``ProviderRegistry`` by the
    composition root), and the read-only Query Port collaborators bound to
    the active request, so that every write and its audit event commit in the
    same transaction as the caller's other writes.
    """

    def __init__(
        self,
        repository: CopilotRepository,
        audit: AuditWriter,
        *,
        inference: InferenceProvider,
        applications: ApplicationReader,
        documents: DocumentReader,
        document_texts: DocumentTextReader,
        evidence: EvidenceReader,
        findings: FindingReader,
        policy_results: PolicyResultReader,
        reviews: ReviewReader,
    ) -> None:
        self._repo = repository
        self._audit = audit
        self._inference = inference
        self._applications = applications
        self._documents = documents
        self._document_texts = document_texts
        self._evidence = evidence
        self._findings = findings
        self._policy_results = policy_results
        self._reviews = reviews

    # ------------------------------------------------------------------
    # Session / query / response bookkeeping
    # ------------------------------------------------------------------

    def create_session(
        self,
        user: AuthenticatedUser,
        *,
        application_id: UUID,
        tenant_id: UUID,
        created_by_user_id: UUID,
        correlation_id: str,
    ) -> CopilotSession:
        """
        Create a new Copilot Session for a human reviewer on one application.

        Raises:
            AuthorizationError: If ``user`` lacks ``query:copilot``.
        """
        require_permission(user, Permission.QUERY_COPILOT)
        session = CopilotSession.create(
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=created_by_user_id,
            correlation_id=correlation_id,
        )
        self._repo.create_session(session)

        self._audit.record(
            event_type="COPILOT_SESSION_CREATED",
            entity_type="COPILOT_SESSION",
            entity_id=session.id,
            tenant_id=tenant_id,
            application_id=application_id,
            actor_id=created_by_user_id,
            event_data={"correlation_id": correlation_id},
        )
        return session

    def submit_query(
        self,
        user: AuthenticatedUser,
        session: CopilotSession,
        *,
        question_text: str,
        asked_by_user_id: UUID,
    ) -> CopilotQuery:
        """
        Record a human reviewer's natural-language question on a session.

        Raises:
            AuthorizationError: If ``user`` lacks ``query:copilot``.
        """
        require_permission(user, Permission.QUERY_COPILOT)
        query = CopilotQuery.create(
            session_id=session.id,
            asked_by_user_id=asked_by_user_id,
            question_text=question_text,
        )
        self._repo.append_query(query)

        self._audit.record(
            event_type="COPILOT_QUERY_RECORDED",
            entity_type="COPILOT_QUERY",
            entity_id=query.id,
            tenant_id=session.tenant_id,
            application_id=session.application_id,
            actor_id=asked_by_user_id,
            event_data={"session_id": str(session.id)},
        )
        return query

    def record_response(
        self,
        query: CopilotQuery,
        *,
        answer_text: str,
        prompt_version: str,
        model_version: str,
        citations: Sequence[Citation] = (),
    ) -> CopilotResponse:
        """
        Persist an already-produced response to a query.

        This is the low-level append operation: it persists whatever answer
        the caller supplies. ``generate_response`` is the orchestration
        method that produces that answer via inference and calls this to
        persist it.
        """
        response = CopilotResponse.create(
            query_id=query.id,
            answer_text=answer_text,
            prompt_version=prompt_version,
            model_version=model_version,
            citations=citations,
        )
        self._repo.append_response(response)
        return response

    # ------------------------------------------------------------------
    # Response generation (Sprint 7B)
    # ------------------------------------------------------------------

    def generate_response(
        self, user: AuthenticatedUser, session: CopilotSession, query: CopilotQuery
    ) -> CopilotResponse:
        """
        Generate a grounded response to ``query`` and persist it.

        Flow: classify the query into a prompt identifier (deterministic,
        rule-based — ``mil.copilot.classifier``, no AI) -> assemble the
        application's ``GroundingBundle`` (read-only, via Query Ports) ->
        transform it into a generalized ``InferenceContext`` of
        ``GroundingItem`` entries -> call the injected ``InferenceProvider``
        with the pinned prompt version -> validate every returned citation
        against the grounding set -> persist the resulting
        ``CopilotResponse`` -> record a synchronous
        ``COPILOT_RESPONSE_GENERATED`` audit event -> return the response.

        Hallucination policy (ADR-011 §6): the model is never asked to
        answer beyond the supplied grounding, and its answer is never
        surfaced unless at least one of its citations resolves to a record
        actually present in the grounding set. If the application has no
        governed records yet, or the model's answer cannot be grounded in a
        citation, a fixed, deterministic "insufficient grounding" response is
        persisted and returned instead — never a fabricated answer.

        Determinism: the query text is exactly what the reviewer asked (no
        rewriting), and the grounding set is built solely from the current
        committed state of the governed records — there is no conversation
        memory or other hidden state feeding this call.

        Raises:
            AuthorizationError: If ``user`` lacks ``query:copilot``.
            ProviderVersionMissingError: If the injected ``InferenceProvider``
                cannot report its own version (Principle XII — a provider
                that cannot attribute its output must not be used).
            ProviderError: Re-raised if the provider's returned
                ``model_version`` does not match its own ``version()`` — an
                internal provider consistency violation.
        """
        require_permission(user, Permission.QUERY_COPILOT)

        provider_version = self._inference.version()
        if not provider_version:
            raise ProviderVersionMissingError("InferenceProvider", "version")

        prompt_id = classify_query(query.question_text)
        prompt_version = get_prompt_version(prompt_id)

        bundle = self.assemble_grounding(session.application_id, tenant_id=session.tenant_id)

        # The application record alone (status, id) is context, not evidence —
        # it cannot ground an answer to an explainability question. Only
        # proceed to inference if at least one substantive governed record
        # exists to cite.
        if not (
            bundle.documents
            or bundle.document_texts
            or bundle.evidence
            or bundle.findings
            or bundle.policy_results
            or bundle.review_actions
        ):
            return self._safe_failure_response(
                session,
                query,
                prompt_version=prompt_version,
                model_version=provider_version,
                reason="no_governed_records",
            )

        grounding_items, citation_index = _build_grounding_items(bundle)

        context = InferenceContext(
            application_id=str(session.application_id),
            query=query.question_text,
            prompt_version=prompt_version,
            grounding_items=grounding_items,
        )
        result = self._inference.infer(context)

        if result.model_version != provider_version:
            raise ProviderError(
                f"InferenceProvider returned an InferenceResult with model_version "
                f"{result.model_version!r}, expected {provider_version!r}",
                provider_name="InferenceProvider",
                retryable=False,
            )

        resolved_citations = _resolve_citations(result.evidence_citations, citation_index)
        if not resolved_citations:
            return self._safe_failure_response(
                session,
                query,
                prompt_version=result.prompt_version,
                model_version=result.model_version,
                reason="ungrounded_model_response",
            )

        response = self.record_response(
            query,
            answer_text=result.content,
            prompt_version=result.prompt_version,
            model_version=result.model_version,
            citations=resolved_citations,
        )
        self._audit_response_generated(
            session,
            query,
            response,
            citation_count=len(resolved_citations),
            degraded=False,
            reason=None,
        )
        return response

    def _safe_failure_response(
        self,
        session: CopilotSession,
        query: CopilotQuery,
        *,
        prompt_version: str,
        model_version: str,
        reason: str,
    ) -> CopilotResponse:
        """
        Persist and return the fixed "insufficient grounding" response.

        Carries no citations — it asserts nothing about the application, so
        it is not subject to the "responses without citations are invalid"
        rule that governs grounded, claim-bearing answers.
        """
        response = self.record_response(
            query,
            answer_text=_INSUFFICIENT_GROUNDING_MESSAGE,
            prompt_version=prompt_version,
            model_version=model_version,
            citations=(),
        )
        self._audit_response_generated(
            session, query, response, citation_count=0, degraded=True, reason=reason
        )
        return response

    def _audit_response_generated(
        self,
        session: CopilotSession,
        query: CopilotQuery,
        response: CopilotResponse,
        *,
        citation_count: int,
        degraded: bool,
        reason: str | None,
    ) -> None:
        event_data: dict[str, object] = {
            "query_id": str(query.id),
            "prompt_version": response.prompt_version,
            "model_version": response.model_version,
            "citation_count": citation_count,
            "degraded": degraded,
        }
        if reason is not None:
            event_data["degraded_reason"] = reason
        self._audit.record(
            event_type="COPILOT_RESPONSE_GENERATED",
            entity_type="COPILOT_RESPONSE",
            entity_id=response.id,
            tenant_id=session.tenant_id,
            application_id=session.application_id,
            actor_id=query.asked_by_user_id,
            event_data=event_data,
        )

    # ------------------------------------------------------------------
    # Session lifecycle for HTTP integration (Sprint 7C)
    # ------------------------------------------------------------------

    def start_or_resume_session(
        self,
        user: AuthenticatedUser,
        *,
        application_id: UUID,
        tenant_id: UUID,
        created_by_user_id: UUID,
        session_id: UUID | None,
        correlation_id: str,
    ) -> CopilotSession:
        """
        Resume an existing session (if ``session_id`` is given and belongs to
        this application and tenant), or create a new one.

        Raises:
            AuthorizationError: If ``user`` lacks ``query:copilot``.
            NotFoundError: If ``session_id`` is given but does not identify a
                session belonging to ``application_id`` within ``tenant_id``.
        """
        require_permission(user, Permission.QUERY_COPILOT)
        if session_id is not None:
            session = self._repo.get_session(session_id)
            if (
                session is None
                or session.application_id != application_id
                or session.tenant_id != tenant_id
            ):
                raise NotFoundError("CopilotSession", session_id)
            return session
        return self.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=created_by_user_id,
            correlation_id=correlation_id,
        )

    def get_session(self, user: AuthenticatedUser, session_id: UUID) -> CopilotSession:
        """
        Return a Copilot Session by id, scoped to the caller's tenant.

        Raises:
            AuthorizationError: If ``user`` lacks ``query:copilot``.
            NotFoundError: If no session with ``session_id`` exists within the
                caller's tenant. A session belonging to a different tenant is
                reported identically to a missing one (tenant isolation must
                not be observable as a distinct error).
        """
        require_permission(user, Permission.QUERY_COPILOT)
        session = self._repo.get_session(session_id)
        if session is None or session.tenant_id != user.tenant_id:
            raise NotFoundError("CopilotSession", session_id)
        return session

    def get_latest_session_for_application(
        self, user: AuthenticatedUser, application_id: UUID, *, tenant_id: UUID
    ) -> CopilotSession:
        """
        Return the most recently created Copilot Session for an application.

        Raises:
            AuthorizationError: If ``user`` lacks ``query:copilot``.
            NotFoundError: If the application does not exist, or no Copilot
                session has been started for it yet.
            ScopeViolationError: If the application does not belong to
                ``tenant_id``.
        """
        require_permission(user, Permission.QUERY_COPILOT)
        application = self._applications.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application", application_id)
        if application.tenant_id != tenant_id:
            raise ScopeViolationError(
                "Application does not belong to the requesting tenant",
                details={
                    "application_id": str(application_id),
                    "requesting_tenant_id": str(tenant_id),
                },
            )
        session = self._repo.get_latest_session_for_application(application_id)
        if session is None:
            raise NotFoundError("CopilotSession", application_id)
        return session

    def get_history(
        self, user: AuthenticatedUser, session: CopilotSession
    ) -> list[tuple[CopilotQuery, CopilotResponse | None]]:
        """
        Return the ordered query/response history for a session.

        Records a synchronous ``COPILOT_RESPONSE_VIEWED`` audit event for
        every response actually returned — a data-access log distinct from
        ``COPILOT_RESPONSE_GENERATED`` (Principle V: full auditability of
        data access).

        Raises:
            AuthorizationError: If ``user`` lacks ``query:copilot``.
        """
        require_permission(user, Permission.QUERY_COPILOT)
        history = self._repo.get_history(session.id)
        for _query, response in history:
            if response is not None:
                self._audit.record(
                    event_type="COPILOT_RESPONSE_VIEWED",
                    entity_type="COPILOT_RESPONSE",
                    entity_id=response.id,
                    tenant_id=session.tenant_id,
                    application_id=session.application_id,
                    actor_id=user.user_id,
                    event_data={"session_id": str(session.id)},
                )
        return history

    # ------------------------------------------------------------------
    # Grounding assembly (read-only, via Query Ports — ADR-010)
    # ------------------------------------------------------------------

    def assemble_grounding(self, application_id: UUID, *, tenant_id: UUID) -> GroundingBundle:
        """
        Assemble an application-scoped, read-only grounding bundle.

        Reads Application, Document, Evidence, Finding, PolicyResult, and
        Review data exclusively through the injected Query Ports — never by
        importing another bounded context's repository or service.

        Raises:
            NotFoundError: If no application exists with ``application_id``.
            ScopeViolationError: If the application does not belong to
                ``tenant_id`` (Principle V — AI context isolation: grounding
                must never cross a tenant boundary).
        """
        application = self._applications.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application", application_id)
        if application.tenant_id != tenant_id:
            raise ScopeViolationError(
                "Application does not belong to the requesting tenant",
                details={
                    "application_id": str(application_id),
                    "requesting_tenant_id": str(tenant_id),
                },
            )

        documents = tuple(self._documents.get_for_application(application_id))
        document_texts = tuple(self._document_texts.get_for_application(application_id))
        evidence = tuple(self._evidence.get_for_application(application_id))
        findings = tuple(self._findings.get_for_application(application_id))

        policy_results: list[PolicyResultView] = []
        review_sessions: list[ReviewSessionView] = []
        review_actions: list[ReviewActionView] = []
        for finding in findings:
            policy_results.extend(self._policy_results.get_for_finding(finding.id))
            review_session = self._reviews.get_session_for_finding(finding.id)
            if review_session is not None:
                review_sessions.append(review_session)
                review_actions.extend(self._reviews.get_actions_for_session(review_session.id))

        return GroundingBundle(
            application_id=application_id,
            application=application,
            documents=documents,
            evidence=evidence,
            findings=findings,
            policy_results=tuple(policy_results),
            review_sessions=tuple(review_sessions),
            review_actions=tuple(review_actions),
            document_texts=document_texts,
        )


# ---------------------------------------------------------------------------
# Grounding -> InferenceContext transformation
#
# This is the one place mortgage domain meaning is attached to the kernel's
# domain-agnostic GroundingItem: the kernel never learns what a "Finding" or
# "PolicyResult" is (its ``kind`` field is an opaque string), but Copilot
# deliberately reuses its own citation-kind constants as that string so a
# returned citation ref can be resolved straight back to a Citation.
# ---------------------------------------------------------------------------


def _build_grounding_items(
    bundle: GroundingBundle,
) -> tuple[tuple[GroundingItem, ...], dict[str, Citation]]:
    """
    Transform a ``GroundingBundle`` into generalized ``GroundingItem`` entries
    and a parallel ``ref -> Citation`` index used to validate returned
    citations.
    """
    items: list[GroundingItem] = [
        GroundingItem(
            kind=APPLICATION,
            ref=str(bundle.application.id),
            summary=f"Application status: {bundle.application.status}",
        )
    ]

    for document in bundle.documents:
        items.append(
            GroundingItem(
                kind=DOCUMENT,
                ref=str(document.id),
                summary=(
                    f"{document.document_type} document '{document.filename}' "
                    f"(status={document.status})"
                ),
            )
        )

    for doc_text in bundle.document_texts:
        summary = doc_text.full_text
        truncated = len(summary) > _DOCUMENT_TEXT_SUMMARY_LIMIT
        if truncated:
            summary = summary[:_DOCUMENT_TEXT_SUMMARY_LIMIT] + " …(truncated)"
        items.append(
            GroundingItem(
                kind=DOCUMENT_TEXT,
                ref=f"doctext-{doc_text.document_id}",
                summary=summary,
                provenance=f"document={doc_text.document_id}#pages={doc_text.page_count}",
                attributes={
                    "extraction_version": doc_text.provider_version,
                    "truncated": "true" if truncated else "false",
                },
            )
        )

    for item in bundle.evidence:
        items.append(
            GroundingItem(
                kind=EVIDENCE,
                ref=str(item.id),
                summary=f"{item.evidence_type}: {item.value_text}",
                provenance=f"document={item.document_id}#page={item.page_number}",
                confidence=item.confidence,
            )
        )

    for finding in bundle.findings:
        items.append(
            GroundingItem(
                kind=FINDING,
                ref=str(finding.id),
                summary=(
                    f"{finding.title} — {finding.rationale} "
                    f"(recommended action: {finding.recommended_action})"
                ),
                attributes={"confidence_label": finding.confidence_label},
            )
        )

    for policy_result in bundle.policy_results:
        items.append(
            GroundingItem(
                kind=POLICY_RESULT,
                ref=str(policy_result.id),
                summary=(
                    f"Policy rule {policy_result.rule_ref}: {policy_result.status} — "
                    f"{policy_result.rationale}"
                ),
                attributes={"policy_version": policy_result.policy_version},
            )
        )

    for action in bundle.review_actions:
        summary = (
            f"Review action {action.action_type}: {action.previous_status} -> {action.new_status}"
        )
        if action.reason:
            summary = f"{summary} (reason: {action.reason})"
        items.append(GroundingItem(kind=REVIEW_ACTION, ref=str(action.id), summary=summary))

    citation_index = {
        item.ref: Citation(kind=item.kind, ref=item.ref, locator=item.provenance) for item in items
    }
    return tuple(items), citation_index


def _resolve_citations(
    raw_refs: Sequence[str], citation_index: dict[str, Citation]
) -> tuple[Citation, ...]:
    """
    Resolve a provider's returned citation refs against the grounding set.

    Any ref that does not match a ``GroundingItem`` actually included in the
    context is dropped rather than trusted — the model cannot cite something
    it was never given (ADR-011 §6: citations MUST be validated against the
    grounding set; an unresolved citation is evidence of an ungrounded claim,
    not something to pass through).
    """
    resolved: list[Citation] = []
    seen_refs: set[str] = set()
    for ref in raw_refs:
        citation = citation_index.get(ref)
        if citation is not None and citation.ref not in seen_refs:
            resolved.append(citation)
            seen_refs.add(citation.ref)
    return tuple(resolved)
