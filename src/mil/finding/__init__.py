"""
Finding Management bounded context.

US2 Sprint 4 scope: generates a Finding from AI inference over the evidence
collected for an application. A Finding is an AI-generated conclusion — it
carries five explainability fields (title, rationale, evidence_summary,
confidence_label, recommended_action) and records its supporting evidence,
inference model version, prompt version, extraction version, workflow run,
and confidence. None of these fields may be absent or empty.

Policy evaluation does not exist yet (a later sprint). This sprint's Finding
is therefore a single, holistic, inference-derived assessment per application
per model version — not one Finding per triggered policy rule. The
``policy_pack_id`` attribution column from the target data model is
intentionally omitted for the same reason ``evidence_items.policy_pack_id``
was omitted in US2 Sprint 3: the Policy Pack bounded context does not exist yet.

The finding lifecycle state machine (EXTRACTED → NEEDS_REVIEW →
VERIFIED/OVERRIDDEN/ESCALATED → RESOLVED) is out of scope for this sprint.
Every Finding is created in the EXTRACTED state and is never mutated
afterwards (append-only, no overwrite behaviour).

Public interface: finding.service.FindingService
"""
