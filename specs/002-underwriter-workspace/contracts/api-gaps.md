# Required Backend API Additions

**This is the single most important finding of this implementation plan.** The Underwriter Workspace specification (002) cannot be built against the API surface that exists today (see `existing-api-surface.md`). The backend's domain logic for Evidence and Finding already exists (`src/mil/evidence/`, `src/mil/finding/` — models, repositories, services), but **none of it is exposed through an HTTP endpoint**. There is also no endpoint for verification/override, notifications, saved views, audit-trail read access, or human-identifier search.

Per the governing instruction, the frontend should consume existing APIs "rather than changing backend contracts unless absolutely necessary." Every endpoint below is judged genuinely necessary — none of these workspace features can be built without them, and none of them require changing an *existing* contract; every one is purely additive, consistent with Constitution Principle IX (Incremental Evolution: "new capabilities MUST be additive"). This document is the hand-off artifact to the backend team; it specifies contracts, not implementation.

## Read Endpoints

| Endpoint (conceptual) | Purpose | Satisfies |
|---|---|---|
| `GET /v1/applications?query=&sort=&filter=&cursor=` | Human-identifier search, filtering, cursor-paginated queue at 100,000+ scale. **Must use a composite `(rank\|sort-column, id)` cursor** (id as tie-breaker) so pagination is stable under both relevance ranking and any sort column; total count should be planner-estimated by default, exact only below a small-row-count threshold — see `plan.md` Search Architecture | 002 FR-009–015, FR-016–025, FR-024 |
| `GET /v1/applications/{id}/evidence` | List evidence items for an application | 002 FR-045–050 |
| `GET /v1/applications/{id}/findings` | List findings, each with resolved evidence refs | 002 FR-031–032, FR-051 |
| `GET /v1/findings/{id}/relationships` | Supports/conflicts-with/derived-from edges for the Knowledge Graph view | 002 FR-064–067 |
| `GET /v1/applications/{id}/audit` | Chronological audit trail for one application | 002 FR-035; Constitution Principle VIII |
| `GET /v1/notifications` | Current user's notifications | 002 FR-084–087 |
| `GET /v1/saved-views` | Current user's (and team-shared) saved queue views | 002 FR-020, FR-070 |

## Write Endpoints

| Endpoint (conceptual) | Purpose | Satisfies |
|---|---|---|
| `POST /v1/findings/{id}/verify` | Record a verification (idempotent, attributed, immutable) | 002 FR-033–034, FR-052; Constitution Principle VIII |
| `POST /v1/findings/{id}/override` | Record an override; requires a non-empty `reason` | 002 FR-033–034, FR-052–053 |
| `POST /v1/findings/{id}/escalate` | Record an escalation; requires a `reason` and target role | 002 FR-054 |
| `POST /v1/saved-views` / `PATCH` / `DELETE` | Manage saved views | 002 FR-020, FR-070 |
| `PATCH /v1/notifications/{id}` | Mark read | 002 FR-085 |

## Streaming Endpoints

| Endpoint (conceptual) | Purpose | Satisfies |
|---|---|---|
| `GET /v1/copilot/sessions/{id}/stream` (SSE) | Progressive token-by-token Copilot response delivery | 002 FR-060 |
| `GET /v1/notifications/stream` (SSE) | Push notification delivery within the 30-second latency bar | 002 FR-084 |

## Authentication Endpoints (added post-analysis)

| Endpoint (conceptual) | Purpose | Satisfies |
|---|---|---|
| `POST /v1/auth/refresh` | Issues a new access token from a short-lived, httpOnly, `SameSite=Strict` refresh cookie scoped to the same origin as the API | `plan.md` Authentication Flow; Constitution Principle V |
| `GET /v1/auth/csrf-token` (or equivalent double-submit mechanism) | Issues a non-httpOnly CSRF token the frontend echoes back as a header on every state-changing request, used alongside `SameSite=Strict` (not as a substitute for it) | `plan.md` Authentication Flow; Constitution Principle V |

This is distinct from, and does not require, the full production-grade (OIDC/JWKS) `IdentityProvider` described below as still out of scope — the refresh/CSRF mechanism is the session layer sitting in front of whichever `IdentityProvider` ultimately verifies the access token, and can be built against the existing dev-bearer flow now, ahead of that larger, separate piece of work.

## Explicit Non-Goals for This Addition Set

- **No existing endpoint's request or response shape changes.** Every addition above is a new route; none require modifying `applications.py`, `documents.py`, `copilot.py`, or `auth.py`'s current contracts.
- **No new bounded context is introduced.** Evidence and Finding already exist as backend bounded contexts (per Constitution Principle VII) — this is exposure of existing domain logic through new API routes, not new domain modeling.
- **Search is not proposed to be backed by a new search service** (see `research.md`); the search endpoint above is expected to be served by the existing Postgres-backed persistence layer (e.g., trigram/full-text indexing), escalated to dedicated search infrastructure only if that later proves insufficient at real production scale.
- **A production-grade (OIDC/JWKS) `IdentityProvider` is a known, pre-existing gap** (see `existing-api-surface.md`) that this plan does not resolve — it is called out here only so it is not lost as a dependency for a production launch, not because this plan proposes to build it.

## Sequencing Recommendation

These additions should be delivered in the order the Workspace specification's own prioritized user stories need them (002, User Scenarios & Testing): Findings/Evidence read + verify/override endpoints unblock User Story 1 (P1) first; search/filtering unblocks User Story 2 (P1) second; Copilot streaming unblocks User Story 3 (P2); relationships/audit-trail unblock User Story 4 (P2); saved views unblock User Story 5 (P2); notifications unblock User Story 6 (P3) last. This mirrors the Workspace specification's own MVP-slice ordering rather than inventing a separate backend delivery sequence.

The Authentication Endpoints above are **not** part of this story-priority sequence — they are a pre-production-cutover dependency, required before the dev-bearer flow is replaced, not before any user story's development work.
