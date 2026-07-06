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

export const FIXTURE_APPLICATION_ID = '11111111-1111-1111-1111-111111111111';
export const FIXTURE_DOCUMENT_ID = '22222222-2222-2222-2222-222222222222';
export const FIXTURE_EVIDENCE_ID = '33333333-3333-3333-3333-333333333333';
export const FIXTURE_FINDING_ID = '44444444-4444-4444-4444-444444444444';

const fixtureApplication = {
  id: FIXTURE_APPLICATION_ID,
  borrowerName: 'Jordan Alvarez',
  loanNumber: '4009123456',
  losReference: 'LOS-0000042',
  status: 'IN_REVIEW',
  assignedReviewer: 'Dev Admin',
  documentCount: 3,
  evidenceCount: 5,
  flaggedFindingCount: 1,
  lastActivityAt: '2026-07-05T14:30:00Z',
  createdAt: '2026-06-20T09:00:00Z',
  slaState: 'onTrack',
};

const fixtureEvidenceItem = {
  id: FIXTURE_EVIDENCE_ID,
  applicationId: FIXTURE_APPLICATION_ID,
  documentId: FIXTURE_DOCUMENT_ID,
  value: '6200.00',
  fieldType: 'income',
  page: 2,
  fieldLocation: { x: 120, y: 340, width: 200, height: 24 },
  extractionConfidence: 'high',
  extractionMethod: 'LLM_EXTRACTION_V1',
  extractionVersion: '2026.06.1',
  extractedAt: '2026-06-21T10:15:00Z',
  verificationStatus: 'unverified',
  conflictsWith: [],
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
  policyVersion: 'policy-pack-2026.2',
};

export const handlers = [
  http.get('/v1/applications/:id', ({ params }) => {
    return HttpResponse.json({ ...fixtureApplication, id: params.id });
  }),

  http.get('/v1/applications/:id/evidence', ({ params }) => {
    return HttpResponse.json([{ ...fixtureEvidenceItem, applicationId: params.id }]);
  }),

  http.get('/v1/applications/:id/findings', ({ params }) => {
    return HttpResponse.json([{ ...fixtureFinding, applicationId: params.id }]);
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
    return HttpResponse.json({ ...fixtureFinding, id: params.id, state: 'verified' });
  }),

  http.post('/v1/findings/:id/override', ({ params }) => {
    return HttpResponse.json({ ...fixtureFinding, id: params.id, state: 'overridden' });
  }),

  http.post('/v1/findings/:id/escalate', ({ params }) => {
    return HttpResponse.json({ ...fixtureFinding, id: params.id, state: 'escalated' });
  }),
];
