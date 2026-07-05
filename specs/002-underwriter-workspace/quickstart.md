# Quickstart: Validating the Frontend Architecture

This is a validation guide, not a build guide — it describes how a senior engineer joining the project confirms the architecture decisions in this plan actually hold, once initial scaffolding exists. It does not contain implementation code.

## Prerequisites

- Backend infrastructure running: `make docker-up && make migrate` (PostgreSQL, Redis, MinIO)
- Backend API running: `make run-api`
- Backend workers running: `make run-worker`
- The API additions listed in `contracts/api-gaps.md` deployed (at minimum: evidence/finding read endpoints and the verify/override write endpoints, to validate User Story 1)
- Frontend dev server running against the local API (see Deployment Strategy in `plan.md` for the same-origin proxy configuration expected in dev)

## Validation Scenarios

These map directly to the Acceptance Scenarios already defined in the Underwriter Workspace specification (002) — this guide does not redefine them, only points to how to exercise them once a working build exists.

1. **Deep link into a seeded application** (validates: TanStack Router type-safe params, FR-005). Navigate directly to an application URL without going through the queue. Confirm the application's identity, findings, and evidence render without a client-side redirect through an intermediate list view.

2. **Search by borrower name at scale** (validates: routing search-params, TanStack Query caching, FR-009–015). Against a seeded dataset of 100,000+ applications (see 002 Success Criteria SC-001, SC-010), confirm a search returns and renders results in under the specified time budget, and that clearing the search restores the newest-first queue without a full page reload.

3. **Verify a finding, then simulate a network interruption on a second override** (validates: confirmed-not-optimistic writes, FR-034). Confirm the first verification reflects only after server confirmation; on the interrupted second action, confirm the typed override reason is preserved and retryable, never silently lost.

4. **Open evidence from a finding, then the source document from that evidence** (validates: PDF.js highlight-overlay coordinate mapping, FR-032, FR-040). Confirm the exact page and highlighted region render correctly, including after changing zoom level.

5. **Ask the Copilot a grounded question, then an ungrounded one** (validates: SSE streaming, citation resolution, FR-057–060). Confirm the grounded answer streams progressively and its citation opens the correct evidence; confirm the ungrounded question returns the explicit insufficient-evidence state, not a fabricated answer.

6. **Run the full keyboard-only pass** (validates: FR-088, Design System accessibility requirements). Complete User Story 1 end-to-end using only the keyboard, including the command palette, without ever touching a pointer device.

7. **Run the automated accessibility gate** (validates: Design System SC-004, SC-008, SC-009). Confirm the Storybook `a11y` addon and the Playwright/axe-core CI check both report zero critical/serious violations on the built component set.

## What "Done" Looks Like for This Plan

The plan is validated, not the feature — full feature validation belongs to `/speckit-tasks` and implementation. This guide confirms the *architecture* holds: routing and caching choices support deep-linking and scale; the confirmed-write policy is actually enforced, not just documented; the PDF highlight layer is technically feasible; the streaming mechanism actually delivers progressive content; and the accessibility gate is a real, automated, CI-enforced check rather than an aspiration.
