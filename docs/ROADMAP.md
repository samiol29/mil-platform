# MIL — Roadmap

MIL (Mortgage Intelligence Layer) is an **AI-assisted underwriting
intelligence layer**, not a Loan Origination System (LOS) and not a lending
decision engine. This roadmap documents what's already built, what's
intentionally left out of the MVP and why, and what's realistically next —
so future work builds on an accurate picture of the system rather than
re-discovering these boundaries from scratch.

Nothing in this document is implemented. It is a record of intent.

---

## Completed MVP

The full underwriting journey — Application → Borrowers → Document Upload →
OCR/Extraction → Evidence → Findings → Policy Evaluation → Human Review
(Verify/Override/Escalate) → Timeline → Audit — is built and verified live
against the real backend and real Gemini API (RC1 stabilization pass,
2026-07-10). Explainability (five required fields on every `Finding`),
traceability (evidence → document jump, finding → evidence chips, policy →
finding grouping), and auditability (an immutable, append-only audit trail
distinct from the human-readable Timeline narrative) are enforced at the
type/domain level, not just in the UI. An enterprise-grade presentation
layer (Phase 11) and a final consistency/refinement pass (Phase 12) are also
complete. See `docs/deployment/RC1_RELEASE_CHECKLIST.md` for the detailed,
current-state checklist this roadmap builds on.

## Deferred by design

These are not missing features — they're explicit, documented architectural
decisions for this MVP, confirmed by direct backend inspection at multiple
points across this project (not assumptions):

- **No policy rule engine.** `PolicyPack`/`PolicyRule` exist as ORM models
  with real `name`/`jurisdiction`/`version` columns, but there is no HTTP
  route to create, list, or resolve one, and the registered
  `PolicyProvider` is a `MockPolicyProvider` — real rule-level evaluation
  logic doesn't exist yet. The backend has no concept of "a rule that
  passed silently" — a `Finding` is only ever created when something is
  flagged, so "which checks passed" is not recoverable data, not just
  unsurfaced data. The frontend's Policy region is honest about this limit
  by design (a permanent, non-dismissable disclosure), not an
  unfinished screen.
- **No production `IdentityProvider`.** Authentication is `DevBearerIdentityProvider`
  (a literal `"dev"` bearer token) everywhere, including this RC1 pass — a
  real OIDC/JWKS provider is a separate, tracked delivery per
  `docs/deployment/README.md`.
- **No distributed job queue.** The `RedisJobQueue`/in-memory `JobQueue`
  implementations have no redelivery/visibility-timeout for a worker that
  dies mid-job (confirmed live this RC1 pass: a lost POLICY job). This is
  explicitly documented in `docs/deployment/README.md` §1 as the reason the
  platform is development-only today — "not a distributed production
  deployment" until a broker-backed `JobQueue`/`EventBus` exists.
- **No borrower PII storage.** Party records carry only a non-PII
  `display_name` — full personal details (SSN, DOB, address, etc.) are
  assumed to live in the LOS and are never stored in MIL. This is why
  universal search (below) can match borrower *name* today but can never
  match SSN-last-4, email, phone, or property address without a real,
  separate architectural decision about what PII MIL is allowed to hold.
- **No AI-driven lending decisions.** Every finding ends at
  `recommendedAction` — a suggestion, never an approval/denial. This is
  the core Engineering Constitution principle (human-in-the-loop) and is
  not something any roadmap item below should erode.

## Future enhancements

### Version 2

- **LOS Integration.** Real `los_reference`/`loan_number` from an external
  Loan Origination System instead of `generateDemoIdentifiers()` (Phase 12)
  — the seam is deliberately isolated to that one function; swapping it for
  a real LOS call requires no other frontend change.
- **Borrower Identity Resolution / cross-application borrower search.**
  Matching the same real person across multiple applications — genuinely
  new backend work (an identity-resolution service), not a frontend gap.
- **Policy Rule Engine + Policy Pack Administration.** A real rule-level
  evaluation engine, plus the missing create/activate/deactivate API routes
  for `PolicyPack`/`PolicyRule` (confirmed via this RC1 pass: none exist
  today, not even a seed script — a `PolicyPack` had to be created directly
  via the domain model for RC1 verification purposes). This is the
  single highest-leverage next step: every application's Policy region is
  currently sparse purely because there is nothing to evaluate against.
- **Universal Search.** The Application Queue and Command Palette already
  share one `search`-enabled `GET /v1/applications` query (matching LOS
  reference, loan number, application ID, and borrower name via a plain
  `ILIKE` `or_()` clause — confirmed fully implemented, not partial).
  Extending it to more fields (e.g. a document's original filename) is a
  small, additive change to that same `or_()` clause. Extending it to
  borrower PII (SSN-last-4, email, phone, property address) requires the
  PII-storage decision noted above first — not a query change.
- **Analytics Dashboard.** Portfolio-level metrics beyond the current
  per-application/queue views — genuinely new aggregate-computation work,
  not extending an existing screen.
- **Operational Monitoring.** A dedicated ops view over worker health, job
  queue depth, and provider latency (the backend already emits some of this
  via `GET /v1/metrics`/`InMemoryMetricEmitter` — this would be the first
  UI consumer of it).

### Version 3

- **Borrower Portal.** A borrower-facing surface (document upload,
  application status) — a different authentication/authorization model
  entirely from the internal reviewer tools this MVP is built for.
- **Real-time notifications.** Push updates as processing/review progresses
  — needs the same broker-backed event infrastructure noted above under
  "no distributed job queue," so it's sequenced after that.
- **Collaboration / comments.** `ReviewComment` exists as a domain model
  server-side (`src/mil/review/service.py`) with **no HTTP route** —
  confirmed by direct inspection multiple times across this project. The
  backend seam already exists; building the route + UI is the actual work.
- **AI Application Chat ("Evidence Copilot").** A `mil.copilot` bounded
  context already exists server-side (grounded Q&A over an application's
  evidence, with citation-validation against a scoped grounding set) — this
  is partially built, not greenfield; finishing/exposing it is the
  remaining work.
- **Fraud relationship graph.** Cross-application/cross-borrower pattern
  detection — depends on Borrower Identity Resolution (v2) existing first.
- **Multi-bank tenancy.** The domain model is already tenant-scoped
  (`tenant_id` on every aggregate) — this would be about onboarding,
  isolation guarantees, and per-tenant configuration (e.g. per-tenant
  Policy Packs), not a schema change.
- **Advanced reporting.** Compliance/regulatory report generation from the
  audit trail — the audit trail itself is already append-only and complete;
  this is a presentation/export layer over data that already exists.

---

## A note on sequencing

The single highest-leverage next step, by a wide margin, is **Policy Pack
Administration** (v2): almost every "the Policy region feels sparse" or
"policy_version is always null" observation across this entire project
traces back to the fact that no application has ever had an active Policy
Pack to evaluate against, because nothing can create one. Fixing that one
gap makes the Policy region, the Overview pipeline's "Policy" stage, and the
Findings region's policy-attribution line all substantially more meaningful
without touching any of their existing frontend code.
