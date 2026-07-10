import { describe, expect, it } from 'vitest';

import { detectDocumentType, hasUnrecognizedExtension } from './documentTypeDetection';

describe('detectDocumentType', () => {
  it.each([
    ['jamie_paystub_march.pdf', 'PAYSLIP'],
    ['payslip-2026-01.pdf', 'PAYSLIP'],
    ['2025_W2.pdf', 'W2'],
    ['tax-return-2024.pdf', 'TAX_RETURN'],
    ['chase_bank_statement.pdf', 'BANK_STATEMENT'],
    ['drivers_license.jpg', 'IDENTITY_DOCUMENT'],
    ['passport_scan.png', 'IDENTITY_DOCUMENT'],
    ['home_appraisal_report.pdf', 'VALUATION_REPORT'],
    ['credit_report.pdf', 'CREDIT_REPORT'],
    ['insurance_policy.pdf', 'INSURANCE_DOCUMENT'],
    ['random_scan_001.pdf', 'OTHER'],
  ] as const)('detects %s as %s', (filename, expected) => {
    expect(detectDocumentType(filename)).toBe(expected);
  });
});

describe('hasUnrecognizedExtension', () => {
  it('accepts every documented supported extension', () => {
    for (const filename of ['a.pdf', 'a.jpg', 'a.jpeg', 'a.png', 'a.tif', 'a.tiff', 'a.zip']) {
      expect(hasUnrecognizedExtension(filename)).toBe(false);
    }
  });

  it('flags an unrecognized extension', () => {
    expect(hasUnrecognizedExtension('notes.docx')).toBe(true);
  });

  it('flags a file with no extension', () => {
    expect(hasUnrecognizedExtension('README')).toBe(true);
  });
});
