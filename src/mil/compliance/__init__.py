"""Security & Compliance bounded context (spec 005-enterprise-platform §16,
Wave 4).

Operationalizes Constitution Principle V (Security & Privacy by Design)
and Principle XI (Regulatory Alignment) as concrete platform capabilities:

- ``DataRetentionPolicy`` — a configurable, per-tenant, per-data-category
  retention policy. ``DELETE`` is disallowed for ``AUDIT_EVENT``/
  ``EVIDENCE`` categories at **both** the domain layer (this module) and
  the database layer (a ``CHECK`` constraint in the migration) — audit
  immutability (Principle VIII) is structurally protected, not just a code
  path that could be bypassed.
- ``ConsentRecord`` — an explicit, timestamped, versioned consent record
  (e.g. captured at Customer Portal account activation, §12) — never
  inferred from usage.

The compliance access-log report (FR-SEC-003 — "list every access to
Application X's data in the last 90 days") is deliberately **not** a
persisted ``ComplianceReportRequest``/async job in this implementation —
see this module's own composition layer (``mil.api.deps``'s
``ComplianceWorkspace``) and the spec's own §16 implementation-correction
note for why: it is a direct, on-demand query over the existing, already-
persisted ``AuditEvent`` table, exactly like every other Wave 3/4 "current-
state snapshot" scope reduction in this platform (no new parallel logging
mechanism, matching FR-SEC-003's own explicit requirement).

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""
