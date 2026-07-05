"""
Review bounded context (Engineering Constitution Principle I — Human
Decision Authority).

US2 Sprint 6 scope: manages the human review of AI-generated, policy-evaluated
Findings. A ``ReviewSession`` is created automatically (Review worker, in
response to ``PolicyEvaluated``) in ``PENDING_REVIEW`` status; every
subsequent transition (assign, approve, reject, override) is driven
exclusively by an authenticated human actor — no AI component may render a
verdict. Every action, including every override, is recorded permanently as
an immutable ``ReviewAction`` row with full attribution (actor, timestamp,
reason, previous/new status, previous/new value).

Review never writes to ``finding.findings`` — Finding rows are immutable
(Sprint 4) and are only ever referenced by id.

Escalation, verification-of-evidence, and any Copilot/notification/reporting
integration are out of scope for this sprint.

Public interface: review.service.ReviewService
"""
