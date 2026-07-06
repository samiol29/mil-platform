# Frontend Integration Contract

**Purpose**: a factual, verified-against-the-running-API reference for whoever adapts a new
presentation layer onto this backend. Everything here was confirmed against the live server on
2026-07-06 (`curl` + the generated OpenAPI schema), not inferred from code reading alone.
Supersedes `existing-api-surface.md` for endpoint inventory purposes (that file is a planning-time
snapshot and is now missing several endpoints); this file is the current contract.

**Scope boundary**: this document describes what exists today. It does not propose changes. If the
incoming frontend needs something not listed here, that is a new backend requirement to negotiate
explicitly — do not assume a gap will resolve itself during the merge.

---

## 1. Full endpoint inventory

Confirmed live via `GET /v1/openapi.json` against a running server — this is the actual registered
route table, not a doc that can drift from the code.

| Method | Path | Notes |
|---|---|---|
| POST | `/v1/applications` | Create application |
| GET | `/v1/applications` | List applications — **paginated envelope**, see §3 |
| GET | `/v1/applications/{application_id}` | Get one application |
| POST | `/v1/applications/{application_id}/submit` | DRAFT → SUBMITTED (requires ≥1 APPLICANT party) |
| POST | `/v1/applications/{application_id}/withdraw` | → WITHDRAWN |
| POST | `/v1/applications/{application_id}/parties` | Add a party |
| GET | `/v1/applications/{application_id}/parties` | List parties — bare array |
| DELETE | `/v1/applications/{application_id}/parties/{party_id}` | Remove a party |
| POST | `/v1/applications/{application_id}/documents` | Upload (multipart: `file`, `document_type`, optional `party_id`) |
| GET | `/v1/applications/{application_id}/documents` | List documents — bare array |
| GET | `/v1/applications/{application_id}/documents/{document_id}` | Document metadata |
| GET | `/v1/applications/{application_id}/documents/{document_id}/content` | Raw file bytes (for the PDF viewer) |
| GET | `/v1/applications/{application_id}/evidence` | List evidence — bare array |
| GET | `/v1/applications/{application_id}/findings` | List findings — bare array |
| GET | `/v1/applications/{application_id}/audit` | Full audit trail — bare array |
| GET | `/v1/applications/{application_id}/copilot` | Latest Copilot session for the application |
| POST | `/v1/findings/{finding_id}/verify` | Approve a finding |
| POST | `/v1/findings/{finding_id}/override` | Override (body: `reason`, `previous_value`, `new_value`) |
| POST | `/v1/findings/{finding_id}/escalate` | Escalate (body: `reason`, `target_role`, optional `target_user_id`) |
| POST | `/v1/copilot/query` | Ask Copilot a question about an application |
| GET | `/v1/copilot/sessions/{session_id}` | Session metadata |
| GET | `/v1/copilot/sessions/{session_id}/history` | Ordered query/response history |
| GET | `/v1/me` | Current authenticated user (`user_id`, `tenant_id`, `roles`, `email`, `display_name`) |
| GET | `/v1/health`, `/v1/live`, `/v1/ready`, `/v1/metrics` | Ops endpoints, no auth |

**Not present**: no Policy Pack admin endpoint (create/activate a pack) exists anywhere — see
Section 6 of the stabilization audit. No Application Queue / search / filter / pagination-by-query
endpoint exists beyond the bare list in §3. No borrower/party identity-resolution endpoint (see the
architecture review delivered alongside this document).

## 2. Authentication

`Authorization: Bearer <token>`, verified by an `IdentityProvider`.

- **Development**: the literal token `dev` resolves to a built-in ADMIN principal
  (`user_id=00000000-0000-4000-8000-000000000001`,
  `tenant_id=00000000-0000-4000-8000-000000000002`) — or a Base64URL-encoded JSON object with
  `user_id`, `tenant_id`, and optional `roles`/`email`/`display_name`, prefixed `dev.`.
- **No signature-verifying (OIDC/JWKS) provider exists yet.** `build_container` fails fast rather
  than accept unsigned tokens outside development — a real, already-known backend dependency for
  any non-development deployment, not something this integration introduces.
- No CORS middleware is configured. A same-origin deployment (frontend and API behind one gateway,
  or a dev-server proxy — see the current frontend's `vite.config.ts` `/v1 → localhost:8000` proxy)
  is the assumption baked into this. If the new frontend is served from a different origin, CORS
  must be added first.
- RBAC roles and their granted permissions live in `mil.kernel.security.ROLE_PERMISSIONS`
  (`Role.UNDERWRITER`, `VERIFICATION_OFFICER`, `CREDIT_ANALYST`, `RISK_ANALYST`,
  `COMPLIANCE_OFFICER`, `AUDIT_TEAM`, `OPERATIONS_MANAGER`, `RELATIONSHIP_MANAGER`, `ADMIN`,
  `SERVICE_ACCOUNT`). `AUDIT_TEAM`/`COMPLIANCE_OFFICER`/`RISK_ANALYST` are read-only for
  evidence/findings — verified/enforced server-side by `require_permission`, not just a frontend
  convention. A new frontend must not assume every authenticated user can act on a finding.

## 3. Response shape — READ THIS BEFORE WIRING LIST VIEWS

**One endpoint returns a paginated envelope; every other list endpoint returns a bare array.** This
inconsistency is real, confirmed against the live OpenAPI schema, and cost real debugging time
during this session's own frontend fix — do not assume all lists share one shape.

```jsonc
// GET /v1/applications  →  ApplicationListResponse
{ "items": [ { /* ApplicationResponse */ } ], "total": 9, "page": 1, "page_size": 20 }

// GET /v1/applications/{id}/documents  →  bare array
[ { /* DocumentResponse */ }, ... ]

// Same bare-array shape for: /evidence, /findings, /parties, /audit
```

All object fields are **snake_case** (standard FastAPI/Pydantic convention: `los_reference`,
`content_hash`, `occurred_at`, `evidence_item_count`, etc.) — there is no camelCase transform on the
wire. (The previous frontend applied a `camelCaseKeysDeep` transform in its axios response
interceptor; that was a frontend-side convention, not a backend contract — the new frontend can
keep snake_case, add its own transform, or do whatever it wants, but should not assume the backend
will ever emit camelCase.)

## 4. Error shape

Every error response (auth failures, validation, conflicts, not-found, unhandled exceptions) has
the same envelope, produced by `mil.api.errors.register_error_handlers`:

```jsonc
{ "code": "CONFLICT", "message": "...", "request_id": null, "details": [] }
```

`code` is a stable string enum (`ErrorCode` in `mil.kernel.errors`) — e.g. `CONFLICT`,
`NOT_FOUND`, `VALIDATION_ERROR`, `AUTHORIZATION_ERROR`, `INVALID_STATE_TRANSITION`,
`INTERNAL_ERROR`. HTTP status codes are mapped consistently (409/404/422/403/500 respectively) — a
new frontend can switch on `code` for specific UI treatment rather than parsing `message`, which is
free text meant for humans, not machine matching.

## 5. Identifier format constraint — real, already caused one production-class bug this session

Every UUID field the backend emits **must** be RFC 4122-compliant (valid version nibble `[1-8]` and
variant nibble `[89ab]`) if the frontend uses strict UUID validation (e.g. Zod's `z.uuid()`, which
the previous frontend did). This bit the platform for real: the backend's own development seed
identity used an all-zero placeholder UUID (`00000000-0000-0000-0000-000000000001`), which a strict
frontend validator correctly rejected, crashing the Audit Timeline and Documents views for any
record attributed to that actor. Fixed backend-side (`mil.identity.provider.DEV_USER_ID` is now
`00000000-0000-4000-8000-000000000001`), but the underlying lesson is durable: **if the new
frontend validates UUID shape strictly, verify every UUID-emitting code path (including seed/dev
data, not just "real" generated ids) actually produces valid ones** — do not assume it, check it.

## 6. Duplicate-upload semantics

`POST /v1/applications/{id}/documents` rejects a byte-for-byte duplicate (same SHA-256 content hash
already uploaded to the same application) with `409 CONFLICT`, naming the existing document in the
error `message` and `details.existing_document_id`. A new frontend's upload flow should handle this
distinctly from a generic upload failure (e.g. "this file is already attached" rather than "upload
failed, try again").

## 7. Known operational gaps that affect what a frontend can demo end-to-end

These are backend/product gaps, not contract instability — the API shapes above are stable — but a
frontend integrator should know about them before assuming a fresh environment can complete a full
demo:

- **No Policy Pack admin endpoint.** Any application will hang at the Policy stage forever in a
  fresh environment unless a Policy Pack is created and activated via a script or direct DB access
  (the domain service exists and is fully tested; only the HTTP surface is missing).
- **No dead-letter visibility.** A job that exhausts its retry budget is dropped silently — no
  endpoint surfaces this today.
- **Gemini free-tier quota (20 requests/day)** backs both OCR and Extraction in development. Heavy
  manual testing exhausts it for the rest of the day; the failure mode is clean (`document.
  ingestion_status = "FAILED"`, `ingestion_error` carries the real provider message), not a crash,
  but it does mean a from-scratch demo can silently stop producing evidence if the quota was
  already spent earlier that day.

## 8. What is genuinely stable and safe to build against

- All endpoint paths, methods, and both response shapes in §1/§3.
- The error envelope in §4.
- RBAC permission enforcement (server-side, not just advisory).
- The finding/review state machine (`PENDING_REVIEW → IN_REVIEW → {APPROVED, REJECTED,
  OVERRIDDEN}`, with `ESCALATED` reachable from either and resolvable via the same three terminal
  actions) — see the architecture review for the full entity-relationship account of how Documents,
  Evidence, Findings, and Audit events relate.
- Idempotent replay behavior across the OCR → Extraction → Finding → Policy → Review pipeline (ADR-008).
