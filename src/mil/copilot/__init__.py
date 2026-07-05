"""
Evidence Copilot bounded context.

Provides an evidence-grounded natural language query interface for mortgage
reviewers. The Copilot constructs its context window from governed records
scoped strictly to the queried application and the requesting user's
permissions. Data from other applications must never appear in a Copilot
response. Delegates inference to InferenceProvider. Every response includes
citations.

Sprint 7B status: session/query/response bookkeeping, grounding assembly, and
grounded response generation are implemented.

- ``copilot.ports`` — consumer-owned, read-only Query Ports (ADR-010) and the
  read-view value objects Copilot needs to assemble a grounding set across
  bounded contexts synchronously, without importing their internals.
- ``copilot.models`` — immutable, append-only ORM models: ``CopilotSession``,
  ``CopilotQuery``, ``CopilotResponse``.
- ``copilot.repository`` — ``CopilotRepository``, the append-only persistence
  gateway for the three models above.
- ``copilot.citations`` — ``Citation``, the reusable, provider-agnostic
  citation abstraction (Application, Document, Evidence, Finding,
  PolicyResult, ReviewAction).
- ``copilot.prompts`` — the prompt identifier / prompt version registry
  (identifiers and pinned version strings only — no prompt text).
- ``copilot.service`` — ``CopilotService``: creates sessions, records queries,
  assembles read-only grounding bundles via the Query Ports, and generates
  grounded responses (``generate_response``) by transforming a
  ``GroundingBundle`` into the generalized ``InferenceContext``, calling the
  injected ``InferenceProvider`` with a pinned prompt version, and validating
  every returned citation against the grounding set. An ungrounded or
  citation-less model answer is never surfaced — a fixed, safe "insufficient
  grounding" response is persisted instead (ADR-011 §6).

Not yet implemented: HTTP endpoints, workers, EventBus/outbox integration,
streaming, conversation memory, embeddings, vector search, prompt editing,
and the port adapters (wired only in a future composition root, still
absent). See ADR-010 (Query Ports) and ADR-011 (Grounded AI Copilot).
"""
