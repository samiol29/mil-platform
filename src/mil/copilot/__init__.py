"""
Evidence Copilot bounded context.

Provides an evidence-grounded natural language query interface for mortgage
reviewers. The Copilot constructs its context window from governed records
scoped strictly to the queried application and the requesting user's
permissions. Data from other applications must never appear in a Copilot
response. Delegates inference to InferenceProvider. Every response includes
citations.

Sprint 7 status: architecture preparation only.
- ``copilot.ports`` — consumer-owned, read-only Query Ports (ADR-010) and the
  read-view value objects Copilot needs to assemble a grounding set across
  bounded contexts synchronously, without importing their internals.

Not yet implemented (Sprint 7): the CopilotService, grounding assembler,
conversation persistence, HTTP endpoints, and the port adapters (wired only in
the composition root). See ADR-011 (Grounded AI Copilot).
"""
