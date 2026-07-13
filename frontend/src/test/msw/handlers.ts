/**
 * MSW contract-shaped mock handlers (spec 002 tasks.md T044).
 *
 * Shapes mirror `data-model.md`'s entities and `contracts/api-gaps.md`'s
 * endpoint list exactly — field names match what the entity-layer Zod
 * schemas (tasks.md T052–T060) will parse, so these fixtures double as a
 * frontend-side contract expectation, usable before the corresponding
 * backend endpoint exists (this product's frontend and backend teams work
 * in parallel per plan.md's Risks & Mitigations) and in every unit/component
 * test (`server.ts`) or standalone local dev run (`browser.ts`).
 */

import { http, HttpResponse } from 'msw';

import { MINIMAL_PDF_BYTES } from './pdfFixture';

// RFC 4122-compliant (variant nibble in [89ab]) — zod's `z.uuid()` validator
// rejects non-compliant placeholders like `11111111-1111-1111-1111-...`,
// a real gap only a full mutation round-trip test exposes (most tests never
// reach a successful `findingSchema.parse` against these fixtures).
export const FIXTURE_APPLICATION_ID = '11111111-1111-1111-a111-111111111111';
export const FIXTURE_DOCUMENT_ID = '22222222-2222-2222-a222-222222222222';
export const FIXTURE_EVIDENCE_ID = '33333333-3333-3333-a333-333333333333';
export const FIXTURE_FINDING_ID = '44444444-4444-4444-a444-444444444444';

const fixtureApplication = {
  id: FIXTURE_APPLICATION_ID,
  losReference: 'LOS-0000042',
  loanNumber: '4009123456',
  status: 'IN_REVIEW',
  activePolicyPackId: null,
  partyCount: 1,
  createdAt: '2026-06-20T09:00:00Z',
  updatedAt: '2026-06-20T09:00:00Z',
};

const fixtureEvidenceItem = {
  id: FIXTURE_EVIDENCE_ID,
  applicationId: FIXTURE_APPLICATION_ID,
  documentId: FIXTURE_DOCUMENT_ID,
  partyId: null,
  evidenceType: 'gross_monthly_income',
  valueText: '6200.00',
  valueNumeric: null,
  currency: null,
  pageNumber: 1,
  fieldLocation: {
    pageNumber: 1,
    fieldName: 'gross_monthly_income',
    boundingBox: [0.1, 0.42, 0.35, 0.05],
  },
  confidence: 'high',
  extractionMethod: 'LLM_EXTRACTION_V1',
  extractionModelVersion: '2026.06.1',
  extractedAt: '2026-06-21T10:15:00Z',
  supersedesId: null,
  createdAt: '2026-06-21T10:15:00Z',
};

const fixtureDocument = {
  id: FIXTURE_DOCUMENT_ID,
  applicationId: FIXTURE_APPLICATION_ID,
  partyId: null,
  filename: 'bank-statement.pdf',
  documentType: 'BANK_STATEMENT',
  ingestionStatus: 'COMPLETED',
  contentHash: 'a'.repeat(64),
  uploadedAt: '2026-06-20T09:00:00Z',
  uploadedBy: '33333333-3333-3333-a333-333333333333',
  evidenceItemCount: 1,
  pageCount: 1,
  ingestionCompletedAt: '2026-06-20T09:05:00Z',
  ingestionError: null,
  retryCount: 0,
};

const fixtureFinding = {
  id: FIXTURE_FINDING_ID,
  applicationId: FIXTURE_APPLICATION_ID,
  what: 'Reported monthly income does not match the pay stub on file.',
  why: 'The application states $6,500/month; the extracted pay stub value is $6,200/month, a $300 discrepancy.',
  recommendedAction: 'Confirm current income with the borrower or request an updated pay stub.',
  evidenceRefs: [FIXTURE_EVIDENCE_ID],
  confidence: 'high',
  state: 'unreviewed',
  modelVersion: 'gpt-underwriting-2026.06',
  promptVersion: 'finding-v3',
  extractionVersion: '2026.06.1',
  policyVersion: 'policy-pack-2026.2',
  escalatedToRole: null,
  escalatedToUserId: null,
  createdAt: '2026-06-21T10:15:00Z',
};

// Mutable in-memory review state for `fixtureFinding` — a real (if
// minimal) state machine, not a static fixture, so that verify/override/
// escalate visibly change what the findings list subsequently returns
// (exercised by unit tests via MSW's Node server and E2E specs via its
// browser worker; each fresh page load / test file gets a clean module
// instance, so no explicit reset between tests is needed).
let findingReviewState: {
  state: string;
  escalatedToRole: string | null;
  escalatedToUserId: string | null;
} = { state: 'unreviewed', escalatedToRole: null, escalatedToUserId: null };

// Mutable in-memory application/evaluation state (final product polish
// sprint) — a real state machine mirroring the backend's own
// DRAFT -> SUBMITTED transition and FINDING_GENERATION run status, so
// submit/retry-evaluation round trips are exercisable in tests exactly like
// `findingReviewState` above.
let applicationStatus: string = fixtureApplication.status;
let evaluationState: {
  status: string;
  errorMessage: string | null;
  retryable: boolean;
  startedAt: string | null;
  completedAt: string | null;
} = {
  status: 'COMPLETED',
  errorMessage: null,
  retryable: false,
  startedAt: '2026-06-20T09:05:00Z',
  completedAt: '2026-06-20T09:10:00Z',
};

export const handlers = [
  http.get('/v1/applications/:id', ({ params }) => {
    return HttpResponse.json({ ...fixtureApplication, id: params.id, status: applicationStatus });
  }),

  http.post('/v1/applications/:id/submit', ({ params }) => {
    applicationStatus = 'SUBMITTED';
    return HttpResponse.json({ ...fixtureApplication, id: params.id, status: applicationStatus });
  }),

  http.get('/v1/applications/:id/evaluation', () => {
    return HttpResponse.json(evaluationState);
  }),

  // No assignment exists by default for the fixture application — an honest
  // "not yet assigned" state, same as any real application before an RM/
  // Underwriter is explicitly assigned via `PUT .../assignment`.
  http.get('/v1/applications/:id/assignment', () => {
    return HttpResponse.json(null);
  }),

  http.post('/v1/applications/:id/retry-evaluation', ({ params }) => {
    evaluationState = {
      status: 'RUNNING',
      errorMessage: null,
      retryable: false,
      startedAt: '2026-06-21T12:00:00Z',
      completedAt: null,
    };
    return HttpResponse.json({ ...fixtureApplication, id: params.id, status: applicationStatus });
  }),

  http.get('/v1/applications/:id/evidence', ({ params }) => {
    return HttpResponse.json([{ ...fixtureEvidenceItem, applicationId: params.id }]);
  }),

  http.get('/v1/applications/:id/findings', ({ params }) => {
    return HttpResponse.json([
      { ...fixtureFinding, applicationId: params.id, ...findingReviewState },
    ]);
  }),

  http.get('/v1/applications/:id/documents', ({ params }) => {
    return HttpResponse.json([{ ...fixtureDocument, applicationId: params.id }]);
  }),

  http.get('/v1/applications/:applicationId/documents/:documentId/content', () => {
    return new HttpResponse(MINIMAL_PDF_BYTES, {
      headers: { 'Content-Type': 'application/pdf' },
    });
  }),

  http.post('/v1/applications/:applicationId/documents/:documentId/retry', ({ params }) => {
    return HttpResponse.json({
      ...fixtureDocument,
      id: params.documentId,
      applicationId: params.applicationId,
      ingestionStatus: 'PENDING',
      ingestionError: null,
      retryCount: fixtureDocument.retryCount + 1,
    });
  }),

  http.get('/v1/applications/:id/audit', ({ params }) => {
    return HttpResponse.json([
      {
        id: '55555555-5555-5555-5555-555555555555',
        applicationId: params.id,
        eventType: 'APPLICATION_CREATED',
        actor: 'Dev Admin',
        timestamp: '2026-06-20T09:00:00Z',
        payload: {},
      },
    ]);
  }),

  http.post('/v1/findings/:id/verify', ({ params }) => {
    findingReviewState = { state: 'verified', escalatedToRole: null, escalatedToUserId: null };
    return HttpResponse.json({ ...fixtureFinding, id: params.id, ...findingReviewState });
  }),

  http.post('/v1/findings/:id/override', ({ params }) => {
    findingReviewState = { state: 'overridden', escalatedToRole: null, escalatedToUserId: null };
    return HttpResponse.json({ ...fixtureFinding, id: params.id, ...findingReviewState });
  }),

  http.post('/v1/findings/:id/escalate', async ({ params, request }) => {
    const body = (await request.json()) as { target_role?: string; target_user_id?: string | null };
    findingReviewState = {
      state: 'escalated',
      escalatedToRole: body.target_role ?? null,
      escalatedToUserId: body.target_user_id ?? null,
    };
    return HttpResponse.json({ ...fixtureFinding, id: params.id, ...findingReviewState });
  }),

  // E2E-only: resets `findingReviewState` at the start of a test that
  // mutates it — a fresh `BrowserContext` doesn't guarantee a fresh MSW
  // Service Worker (it can persist across contexts within one browser
  // process/worker), so E2E specs call this explicitly rather than
  // relying on module re-initialization. Never reachable from real
  // application code, which never calls `/__test__/*`.
  http.post('/v1/__test__/reset', () => {
    findingReviewState = { state: 'unreviewed', escalatedToRole: null, escalatedToUserId: null };
    applicationStatus = fixtureApplication.status;
    evaluationState = {
      status: 'COMPLETED',
      errorMessage: null,
      retryable: false,
      startedAt: '2026-06-20T09:05:00Z',
      completedAt: '2026-06-20T09:10:00Z',
    };
    return HttpResponse.json({ ok: true });
  }),
];
