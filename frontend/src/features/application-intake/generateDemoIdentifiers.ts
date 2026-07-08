/**
 * Demo system-identifier generator (Product Experience phase, Phase 12).
 *
 * MIL runs standalone today, with no external LOS connected — but
 * `CreateApplicationRequest`'s `los_reference`/`loan_number` are already
 * fully optional/nullable server-side (`src/mil/api/v1/schemas.py`); nothing
 * backend-side requires them, so generating them client-side for this demo
 * is a frontend-only decision. This function is the deliberate seam: a
 * future LOS integration replaces its body with a real LOS lookup, and
 * nothing else in the intake flow (`IntakeWizard.tsx`, `ApplicationStep.tsx`,
 * `ReviewStep.tsx`) needs to change.
 */

function randomDigits(length: number): string {
  let out = '';
  for (let index = 0; index < length; index += 1) {
    out += Math.floor(Math.random() * 10).toString();
  }
  return out;
}

export interface DemoIdentifiers {
  readonly losReference: string;
  readonly loanNumber: string;
}

export function generateDemoIdentifiers(): DemoIdentifiers {
  return {
    losReference: `LOS-${randomDigits(7)}`,
    loanNumber: randomDigits(10),
  };
}
