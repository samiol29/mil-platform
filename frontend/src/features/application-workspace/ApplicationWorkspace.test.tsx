import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { FIXTURE_APPLICATION_ID } from '../../test/msw/handlers';
import { server } from '../../test/msw/server';
import { ApplicationWorkspace } from './ApplicationWorkspace';
import type { WorkspaceRegion } from './regions';

const DOC_A = 'aaaaaaaa-1111-4111-a111-111111111111';
const DOC_B = 'bbbbbbbb-2222-4222-a222-222222222222';
const EVIDENCE_A = 'cccccccc-3333-4333-a333-333333333333';
const EVIDENCE_B = 'dddddddd-4444-4444-a444-444444444444';
const FINDING_A = 'eeeeeeee-5555-4555-a555-555555555555';

function makeDocument(id: string, filename: string) {
  return {
    id,
    applicationId: FIXTURE_APPLICATION_ID,
    partyId: null,
    filename,
    documentType: 'BANK_STATEMENT',
    ingestionStatus: 'COMPLETED',
    contentHash: `${id.slice(0, 8)}${'0'.repeat(56)}`,
    uploadedAt: '2026-06-20T09:00:00Z',
    uploadedBy: '33333333-3333-3333-a333-333333333333',
    evidenceItemCount: 1,
    pageCount: 1,
    ingestionCompletedAt: '2026-06-20T09:05:00Z',
    ingestionError: null,
  };
}

function makeEvidence(id: string, documentId: string, evidenceType: string) {
  return {
    id,
    applicationId: FIXTURE_APPLICATION_ID,
    documentId,
    partyId: null,
    evidenceType,
    valueText: '6200.00',
    valueNumeric: null,
    currency: null,
    pageNumber: 1,
    fieldLocation: { pageNumber: 1, fieldName: evidenceType, boundingBox: [0.1, 0.4, 0.3, 0.05] },
    confidence: 'high',
    extractionMethod: 'LLM_EXTRACTION_V1',
    extractionModelVersion: '2026.06.1',
    extractedAt: '2026-06-21T10:15:00Z',
    supersedesId: null,
    createdAt: '2026-06-21T10:15:00Z',
  };
}

function mockWorkspaceData() {
  server.use(
    http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/documents`, () =>
      HttpResponse.json([
        makeDocument(DOC_A, 'paystub.pdf'),
        makeDocument(DOC_B, 'bank-statement.pdf'),
      ]),
    ),
    http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/evidence`, () =>
      HttpResponse.json([
        makeEvidence(EVIDENCE_A, DOC_A, 'gross_monthly_income'),
        makeEvidence(EVIDENCE_B, DOC_B, 'account_balance'),
      ]),
    ),
    http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/findings`, () =>
      HttpResponse.json([
        {
          id: FINDING_A,
          applicationId: FIXTURE_APPLICATION_ID,
          what: 'Income mismatch',
          why: 'Reported income differs from the pay stub.',
          evidenceRefs: [EVIDENCE_A],
          confidence: 'high',
          recommendedAction: 'Confirm with borrower.',
          state: 'unreviewed',
          modelVersion: 'v1',
          promptVersion: 'v1',
          extractionVersion: 'v1',
          policyVersion: null,
          escalatedToRole: null,
          escalatedToUserId: null,
          createdAt: '2026-06-21T10:15:00Z',
        },
      ]),
    ),
    http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/parties`, () => HttpResponse.json([])),
  );
}

function Harness({ initialRegion }: { initialRegion: WorkspaceRegion }) {
  const [region, setRegion] = useState<WorkspaceRegion>(initialRegion);
  return (
    <ApplicationWorkspace
      applicationId={FIXTURE_APPLICATION_ID}
      region={region}
      onRegionChange={setRegion}
    />
  );
}

function renderWorkspace(initialRegion: WorkspaceRegion) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <Harness initialRegion={initialRegion} />
    </QueryClientProvider>,
  );
}

describe('ApplicationWorkspace — Evidence Workspace (Phase 5)', () => {
  it('groups evidence by its source document, headed by the real filename', async () => {
    mockWorkspaceData();
    renderWorkspace('evidence');

    expect(await screen.findByText('paystub.pdf')).toBeInTheDocument();
    expect(screen.getByText('bank-statement.pdf')).toBeInTheDocument();
    expect(screen.getByText('gross monthly income')).toBeInTheDocument();
    expect(screen.getByText('account balance')).toBeInTheDocument();
  });

  it('shows provenance and confidence, not just the raw value', async () => {
    mockWorkspaceData();
    renderWorkspace('evidence');

    expect((await screen.findAllByText(/Extracted via LLM_EXTRACTION_V1/)).length).toBe(2);
    expect(screen.getAllByRole('meter').length).toBeGreaterThan(0);
  });

  it('shows a reverse "used in finding" link only for evidence a finding actually cites', async () => {
    mockWorkspaceData();
    renderWorkspace('evidence');

    const paystubGroup = (await screen.findByText('paystub.pdf')).closest('div');
    expect(paystubGroup).not.toBeNull();
    if (paystubGroup === null) throw new Error('unreachable');
    expect(within(paystubGroup).getByText('Used in 1 finding →')).toBeInTheDocument();

    const bankGroup = screen.getByText('bank-statement.pdf').closest('div');
    expect(bankGroup).not.toBeNull();
    if (bankGroup === null) throw new Error('unreachable');
    expect(within(bankGroup).queryByText(/Used in \d+ finding/)).not.toBeInTheDocument();
  });

  it('clicking "View in document" on an evidence card switches to the Documents region', async () => {
    mockWorkspaceData();
    renderWorkspace('evidence');
    const user = userEvent.setup();

    const [firstButton] = await screen.findAllByText('View in document');
    await user.click(firstButton);

    // Phase 11: evidence/trace deep links land directly in viewer mode.
    expect(await screen.findByText('← All documents')).toBeInTheDocument();
  });

  it('clicking "View evidence" on a Documents row switches to Evidence, focused on that document', async () => {
    mockWorkspaceData();
    renderWorkspace('documents');
    const user = userEvent.setup();

    const paystubRow = (await screen.findByText('paystub.pdf')).closest('li');
    expect(paystubRow).not.toBeNull();
    if (paystubRow === null) throw new Error('unreachable');
    await user.click(within(paystubRow).getByText('View 1 evidence item →'));

    expect(await screen.findByText('paystub.pdf')).toBeInTheDocument();
  });
});

describe('ApplicationWorkspace — Policy Workspace (Phase 7)', () => {
  it('shows real finding counts and the permanent honest limitation disclosure', async () => {
    mockWorkspaceData();
    renderWorkspace('policy');

    expect(await screen.findByText('No active policy pack')).toBeInTheDocument();
    expect(
      screen.getByText(/This workspace shows findings that were flagged during policy evaluation/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Rule-level detail is not yet available for any evaluation/),
    ).toBeInTheDocument();
  });

  it('shows rule-level triggered/passed breakdown when the backend has recorded it (spec 005 §3)', async () => {
    mockWorkspaceData();
    server.use(
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/policy-results`, () =>
        HttpResponse.json({
          items: [
            {
              id: 'ffffffff-6666-4666-a666-666666666666',
              findingId: FINDING_A,
              applicationId: FIXTURE_APPLICATION_ID,
              policyPackId: '11111111-7777-4777-a777-777777777777',
              policyVersion: 'v1.0.0',
              outcome: 'FLAGGED',
              triggeredRuleKeys: ['INCOME_MISMATCH'],
              evaluatedRuleKeys: ['INCOME_MISMATCH', 'MISSING_DOCUMENT', 'LOW_CONFIDENCE'],
              passedRuleKeys: ['MISSING_DOCUMENT', 'LOW_CONFIDENCE'],
              evaluatedAt: '2026-07-11T00:00:00Z',
              createdAt: '2026-07-11T00:00:00Z',
            },
          ],
        }),
      ),
    );
    renderWorkspace('policy');

    expect(
      await screen.findByText(/Rule-level detail below \(rules evaluated vs\. triggered\)/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Triggered: INCOME_MISMATCH/)).toBeInTheDocument();
    expect(screen.getByText(/Passed: MISSING_DOCUMENT, LOW_CONFIDENCE/)).toBeInTheDocument();
  });

  it('shows the real activePolicyPackId with an honest caption when one exists, never a fabricated name', async () => {
    server.use(
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}`, () =>
        HttpResponse.json({
          id: FIXTURE_APPLICATION_ID,
          losReference: 'LOS-0000042',
          loanNumber: '4009123456',
          status: 'IN_REVIEW',
          activePolicyPackId: 'ffffffff-6666-4666-a666-666666666666',
          partyCount: 1,
          createdAt: '2026-06-20T09:00:00Z',
          updatedAt: '2026-06-20T09:00:00Z',
        }),
      ),
    );
    mockWorkspaceData();
    renderWorkspace('policy');

    expect(await screen.findByText('ffffffff-6666-4666-a666-666666666666')).toBeInTheDocument();
    expect(
      screen.getByText('No policy pack registry endpoint exists yet to resolve this to a name.'),
    ).toBeInTheDocument();
  });

  it('groups findings by their real policyVersion, with a null-version finding in its own "Not yet evaluated" group', async () => {
    mockWorkspaceData();
    renderWorkspace('policy');

    expect(await screen.findByText('Not yet evaluated')).toBeInTheDocument();
    expect(screen.getByText('Income mismatch')).toBeInTheDocument();
  });

  it('clicking an evidence chip in a policy group switches to the Documents region', async () => {
    mockWorkspaceData();
    renderWorkspace('policy');
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /gross_monthly_income/i }));
    // Phase 11: evidence/trace deep links land directly in viewer mode.
    expect(await screen.findByText('← All documents')).toBeInTheDocument();
  });

  it('clicking "View finding" switches to the Findings region and scrolls that finding into view', async () => {
    mockWorkspaceData();
    renderWorkspace('policy');
    const user = userEvent.setup();

    await user.click(await screen.findByText('View finding →'));
    expect(await screen.findByRole('heading', { name: 'Findings' })).toBeInTheDocument();
    expect(screen.getByText('Income mismatch')).toBeInTheDocument();
  });
});

describe('ApplicationWorkspace — honest no-findings messaging (Phase 12)', () => {
  function mockZeroFindings(status: 'IN_PROGRESS' | 'FAILED' | 'COMPLETED') {
    server.use(
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/documents`, () =>
        HttpResponse.json([
          makeDocument(DOC_A, 'paystub.pdf'),
          { ...makeDocument(DOC_B, 'bank-statement.pdf'), ingestionStatus: status },
        ]),
      ),
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/evidence`, () => HttpResponse.json([])),
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/findings`, () => HttpResponse.json([])),
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/parties`, () => HttpResponse.json([])),
    );
  }

  it('Findings region: shows the generic "not yet" message while documents are still processing', async () => {
    mockZeroFindings('IN_PROGRESS');
    renderWorkspace('findings');

    expect(await screen.findByText('No findings yet')).toBeInTheDocument();
    expect(screen.queryByText('No material issues were detected')).not.toBeInTheDocument();
  });

  it('Findings region: shows an honest "no material issues" message only when every document actually COMPLETED', async () => {
    mockZeroFindings('COMPLETED');
    renderWorkspace('findings');

    expect(await screen.findByText('No material issues were detected')).toBeInTheDocument();
    expect(
      screen.getByText('Every document processed successfully without generating any findings.'),
    ).toBeInTheDocument();
  });

  it('Findings region: never reports a clean pass when a document FAILED — a failure is not "no issues"', async () => {
    mockZeroFindings('FAILED');
    renderWorkspace('findings');

    expect(
      await screen.findByText('No findings — but some documents failed to process'),
    ).toBeInTheDocument();
    expect(screen.queryByText('No material issues were detected')).not.toBeInTheDocument();
  });

  it('Policy region: shows the generic "not yet" message while documents are still processing', async () => {
    mockZeroFindings('IN_PROGRESS');
    renderWorkspace('policy');

    expect(
      await screen.findByText('No findings to evaluate against policy yet'),
    ).toBeInTheDocument();
  });

  it('Policy region: collapses to one calm "no material issues" state only when every document actually COMPLETED', async () => {
    mockZeroFindings('COMPLETED');
    renderWorkspace('policy');

    expect(await screen.findByText('No material issues were detected')).toBeInTheDocument();
    expect(screen.queryByText('Active policy pack')).not.toBeInTheDocument();
    expect(screen.queryByText('Awaiting judgment')).not.toBeInTheDocument();
  });

  it('Policy region: never reports a clean pass when a document FAILED', async () => {
    mockZeroFindings('FAILED');
    renderWorkspace('policy');

    expect(
      await screen.findByText('Nothing to evaluate — some documents failed to process'),
    ).toBeInTheDocument();
    expect(screen.queryByText('No material issues were detected')).not.toBeInTheDocument();
  });
});

describe('ApplicationWorkspace — Documents list ⇄ viewer (Phases 8 + 11)', () => {
  async function inspectorTabList() {
    return screen.findByRole('tablist', { name: 'Document inspector sections' });
  }

  it('list mode is the default: the file list renders, the inspector does not', async () => {
    mockWorkspaceData();
    renderWorkspace('documents');

    expect(await screen.findByText('Document Package')).toBeInTheDocument();
    expect(
      screen.queryByRole('tablist', { name: 'Document inspector sections' }),
    ).not.toBeInTheDocument();
  });

  it('opening a document enters viewer mode with the inspector scoped to it', async () => {
    mockWorkspaceData();
    renderWorkspace('documents');
    const user = userEvent.setup();

    await user.click(await screen.findByText('paystub.pdf'));
    const tabs = await inspectorTabList();
    await user.click(within(tabs).getByRole('tab', { name: /Evidence/ }));
    expect(await screen.findByText('gross monthly income')).toBeInTheDocument();
    expect(screen.queryByText('account balance')).not.toBeInTheDocument();
  });

  it('"All documents" returns from viewer mode to the list', async () => {
    mockWorkspaceData();
    renderWorkspace('documents');
    const user = userEvent.setup();

    await user.click(await screen.findByText('paystub.pdf'));
    await inspectorTabList();
    await user.click(screen.getByText('← All documents'));

    expect(await screen.findByText('Document Package')).toBeInTheDocument();
    expect(
      screen.queryByRole('tablist', { name: 'Document inspector sections' }),
    ).not.toBeInTheDocument();
  });

  it('opening a different document scopes the inspector to that document', async () => {
    mockWorkspaceData();
    renderWorkspace('documents');
    const user = userEvent.setup();

    await user.click(await screen.findByText('bank-statement.pdf'));
    const tabs = await inspectorTabList();
    await user.click(within(tabs).getByRole('tab', { name: /Evidence/ }));
    expect(await screen.findByText('account balance')).toBeInTheDocument();
    expect(screen.queryByText('gross monthly income')).not.toBeInTheDocument();
  });

  it('an evidence chip in the inspector jumps within the document (same DocumentJumpTarget mechanism)', async () => {
    mockWorkspaceData();
    renderWorkspace('documents');
    const user = userEvent.setup();

    await user.click(await screen.findByText('paystub.pdf'));
    const tabs = await inspectorTabList();
    await user.click(within(tabs).getByRole('tab', { name: /Evidence/ }));
    expect(await screen.findByText('View in document')).toBeInTheDocument();
  });

  it("the Findings tab in the inspector shows the finding tied to the open document's evidence", async () => {
    mockWorkspaceData();
    renderWorkspace('documents');
    const user = userEvent.setup();

    await user.click(await screen.findByText('paystub.pdf'));
    const tabs = await inspectorTabList();
    await user.click(within(tabs).getByRole('tab', { name: /Findings/ }));
    expect(await screen.findByText('Income mismatch')).toBeInTheDocument();
  });

  it('an evidence-chip deep link from another region lands directly in viewer mode', async () => {
    mockWorkspaceData();
    renderWorkspace('evidence');
    const user = userEvent.setup();

    const [firstButton] = await screen.findAllByText('View in document');
    await user.click(firstButton);

    // Viewer mode, not the list: the slim header's back affordance renders.
    expect(await screen.findByText('← All documents')).toBeInTheDocument();
  });

  it('"Hide details" collapses the inspector so the document takes the full width', async () => {
    mockWorkspaceData();
    renderWorkspace('documents');
    const user = userEvent.setup();

    await user.click(await screen.findByText('paystub.pdf'));
    await inspectorTabList();
    await user.click(screen.getByRole('button', { name: 'Hide details' }));
    expect(
      screen.queryByRole('tablist', { name: 'Document inspector sections' }),
    ).not.toBeInTheDocument();
  });
});

function mockAuditTrail() {
  server.use(
    http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/audit`, () =>
      HttpResponse.json([
        {
          id: 'ffffffff-1111-4111-a111-111111111111',
          applicationId: FIXTURE_APPLICATION_ID,
          eventType: 'DOCUMENT_UPLOADED',
          entityType: 'DOCUMENT',
          entityId: DOC_A,
          actorId: null,
          actorType: 'USER',
          eventData: { original_filename: 'paystub.pdf' },
          occurredAt: '2026-06-20T09:00:00Z',
          sequenceNumber: 1,
        },
        {
          id: 'ffffffff-2222-4222-a222-222222222222',
          applicationId: FIXTURE_APPLICATION_ID,
          eventType: 'REVIEW_FINDING_APPROVED',
          entityType: 'REVIEW_SESSION',
          entityId: 'ffffffff-3333-4333-a333-333333333333',
          actorId: null,
          actorType: 'USER',
          eventData: { finding_id: FINDING_A },
          occurredAt: '2026-06-21T10:20:00Z',
          sequenceNumber: 2,
        },
      ]),
    ),
  );
}

describe("ApplicationWorkspace — Timeline: the application's case history (Phase 9)", () => {
  it('shows a real, friendly narrative for real audit events, grouped and traceable', async () => {
    mockWorkspaceData();
    mockAuditTrail();
    renderWorkspace('timeline');

    expect(await screen.findByText('Document uploaded: paystub.pdf')).toBeInTheDocument();
    expect(await screen.findByText('Finding verified: Income mismatch')).toBeInTheDocument();
  });

  it('a document trace click switches to Documents with that document selected', async () => {
    mockWorkspaceData();
    mockAuditTrail();
    renderWorkspace('timeline');
    const user = userEvent.setup();

    await user.click(await screen.findByText('View document →'));
    // Phase 11: evidence/trace deep links land directly in viewer mode.
    expect(await screen.findByText('← All documents')).toBeInTheDocument();
  });

  it('a finding trace click switches to Findings with that finding scrolled into view', async () => {
    mockWorkspaceData();
    mockAuditTrail();
    renderWorkspace('timeline');
    const user = userEvent.setup();

    await user.click(await screen.findByText('View finding →'));
    expect(await screen.findByRole('heading', { name: 'Findings' })).toBeInTheDocument();
    expect(screen.getByText('Income mismatch')).toBeInTheDocument();
  });

  it('Overview\'s "View full timeline" link navigates to the Timeline region', async () => {
    mockWorkspaceData();
    mockAuditTrail();
    renderWorkspace('overview');
    const user = userEvent.setup();

    await user.click(await screen.findByText('View full timeline →'));
    expect(await screen.findByRole('heading', { name: 'Timeline' })).toBeInTheDocument();
  });
});

describe('ApplicationWorkspace — AI Case Copilot (spec 005 §8)', () => {
  it('shows an honest "no questions yet" state when no Copilot session exists', async () => {
    mockWorkspaceData();
    server.use(
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/copilot`, () =>
        HttpResponse.json({ code: 'NOT_FOUND', message: 'not found' }, { status: 404 }),
      ),
    );
    renderWorkspace('overview');
    const user = userEvent.setup();

    await user.click(await screen.findByText('Ask Copilot about this application'));

    expect(await screen.findByText('No questions asked yet on this application.')).toBeInTheDocument();
  });

  it('renders history with a grounded answer and a clickable document citation', async () => {
    mockWorkspaceData();
    const sessionId = '99999999-9999-4999-a999-999999999999';
    server.use(
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/copilot`, () =>
        HttpResponse.json({
          id: sessionId,
          applicationId: FIXTURE_APPLICATION_ID,
          tenantId: '22222222-2222-4222-8222-222222222222',
          createdByUserId: '33333333-3333-4333-8333-333333333333',
          correlationId: 'corr-1',
          createdAt: '2026-07-11T00:00:00Z',
        }),
      ),
      http.get(`/v1/copilot/sessions/${sessionId}/history`, () =>
        HttpResponse.json({
          sessionId,
          items: [
            {
              queryId: '44444444-4444-4444-8444-444444444444',
              question: 'What evidence supports the income finding?',
              askedByUserId: '33333333-3333-4333-8333-333333333333',
              askedAt: '2026-07-11T00:01:00Z',
              response: {
                id: '55555555-5555-4555-a555-555555555555',
                queryId: '44444444-4444-4444-8444-444444444444',
                sessionId,
                answer: 'The income finding is supported by the pay stub evidence item.',
                promptVersion: 'v1',
                modelVersion: 'gemini-1',
                citations: [{ kind: 'DOCUMENT', ref: DOC_A, locator: '1' }],
                createdAt: '2026-07-11T00:01:05Z',
              },
            },
          ],
        }),
      ),
    );
    renderWorkspace('overview');
    const user = userEvent.setup();

    await user.click(await screen.findByText('Ask Copilot about this application'));

    expect(await screen.findByText(/supported by the pay stub evidence item/)).toBeInTheDocument();
    const citation = screen.getByText(/DOCUMENT:/);
    await user.click(citation);

    // Confirms the DOCUMENT citation reused the existing jump mechanism:
    // the Documents region opens directly in viewer mode (not the list),
    // signposted by its "← All documents" back affordance.
    expect(await screen.findByText('← All documents')).toBeInTheDocument();
  });
});

describe('ApplicationWorkspace — Collaboration (spec 005 §9)', () => {
  it('shows an honest "no comments yet" state, then posts a new comment', async () => {
    mockWorkspaceData();
    let posted: Record<string, unknown> | null = null;
    server.use(
      http.get(`/v1/findings/${FINDING_A}/comments`, () => HttpResponse.json({ items: [] })),
      http.post(`/v1/findings/${FINDING_A}/comments`, async ({ request }) => {
        posted = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: '66666666-6666-4666-a666-666666666666',
            reviewSessionId: '77777777-7777-4777-a777-777777777777',
            authorUserId: '88888888-8888-4888-a888-888888888888',
            commentText: posted.comment_text,
            mentionedUserIds: [],
            editedAt: null,
            deletedAt: null,
            createdAt: '2026-07-11T00:00:00Z',
          },
          { status: 201 },
        );
      }),
    );
    renderWorkspace('findings');
    const user = userEvent.setup();

    await user.click(await screen.findByText('Comments'));
    expect(await screen.findByText('No comments yet on this finding.')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Add a comment'), 'Can compliance confirm this?');
    await user.click(screen.getByRole('button', { name: 'Comment' }));

    await waitFor(() => {
      expect(posted).toMatchObject({ comment_text: 'Can compliance confirm this?' });
    });
  });

  it('shows an existing comment from a real Review Session', async () => {
    mockWorkspaceData();
    server.use(
      http.get(`/v1/findings/${FINDING_A}/comments`, () =>
        HttpResponse.json({
          items: [
            {
              id: '66666666-6666-4666-a666-666666666666',
              reviewSessionId: '77777777-7777-4777-a777-777777777777',
              authorUserId: '88888888-8888-4888-a888-888888888888',
              commentText: 'Please double-check the pay stub math.',
              mentionedUserIds: [],
              editedAt: null,
              deletedAt: null,
              createdAt: '2026-07-11T00:00:00Z',
            },
          ],
        }),
      ),
    );
    renderWorkspace('findings');
    const user = userEvent.setup();

    await user.click(await screen.findByText('Comments'));

    expect(await screen.findByText('Please double-check the pay stub math.')).toBeInTheDocument();
  });
});

describe('ApplicationWorkspace — LOS Integration (spec 005 §2, Wave 2)', () => {
  it('syncs from the LOS and shows the real outcome', async () => {
    mockWorkspaceData();
    const syncEvent = {
      id: '99999999-8888-4888-a888-888888888888',
      applicationId: FIXTURE_APPLICATION_ID,
      direction: 'INBOUND',
      outcome: 'SUCCESS',
      detail: { documentCount: 2 },
      errorMessage: null,
      initiatedByUserId: '11111111-2222-4222-a222-222222222222',
      occurredAt: '2026-07-11T00:00:00Z',
    };
    let syncEvents: (typeof syncEvent)[] = [];
    server.use(
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/los-sync-events`, () =>
        HttpResponse.json({ items: syncEvents }),
      ),
      http.post(`/v1/applications/${FIXTURE_APPLICATION_ID}/los-sync`, () => {
        syncEvents = [syncEvent];
        return HttpResponse.json(syncEvent);
      }),
    );
    renderWorkspace('overview');
    const user = userEvent.setup();

    await user.click(await screen.findByText('LOS Sync — LOS-0000042'));
    await user.click(screen.getByRole('button', { name: 'Sync from LOS' }));

    expect(await screen.findByText(/INBOUND · SUCCESS/)).toBeInTheDocument();
  });
});
