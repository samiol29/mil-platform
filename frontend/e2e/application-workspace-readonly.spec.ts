import { expect, test } from '@playwright/test';

import { FIXTURE_APPLICATION_ID } from '../src/test/msw/handlers';

/**
 * E2E coverage for spec 002 FR-037 / tasks.md T129 (resolves post-analysis
 * finding C3): an auditor/compliance-role session renders the Application
 * Workspace with zero action controls present in the DOM — not
 * merely disabled-but-visible — while all evidentiary content is
 * identical to the underwriter view.
 *
 * `?devRole=` is a dev/E2E-only override (`authProvider.ts`) simulating a
 * read-only role without a real multi-role login flow, which does not
 * exist yet (gated on the production IdentityProvider — see
 * `authProvider.ts`'s own docstring).
 */

test.describe('Application Workspace — read-only role (FR-037)', () => {
  test('a COMPLIANCE_OFFICER session shows findings with no action controls', async ({ page }) => {
    await page.goto(
      `/applications/${FIXTURE_APPLICATION_ID}?region=findings&devRole=COMPLIANCE_OFFICER`,
    );

    // Evidentiary content is identical to the underwriter view.
    await expect(
      page.getByText('Reported monthly income does not match the pay stub on file.'),
    ).toBeVisible();
    await expect(page.getByRole('meter', { name: 'Extraction confidence' })).toBeVisible();

    // No action controls exist in the DOM at all — not disabled, absent.
    await expect(page.getByRole('button', { name: 'Verify' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Override' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Escalate' })).toHaveCount(0);
  });

  test('an AUDIT_TEAM session also renders read-only', async ({ page }) => {
    await page.goto(`/applications/${FIXTURE_APPLICATION_ID}?region=findings&devRole=AUDIT_TEAM`);

    await expect(
      page.getByText('Reported monthly income does not match the pay stub on file.'),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Verify' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Override' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Escalate' })).toHaveCount(0);
  });

  test('an underwriter (default dev role) sees action controls', async ({ page }) => {
    await page.goto(`/applications/${FIXTURE_APPLICATION_ID}?region=findings`);

    await expect(page.getByRole('button', { name: 'Verify' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Override' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Escalate' })).toBeVisible();
  });
});
