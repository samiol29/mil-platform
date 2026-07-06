/**
 * A minimal, valid single-page PDF, built with correctly-computed `xref`
 * byte offsets (not hand-typed magic numbers, which drift the moment the
 * object bodies change) — used by `handlers.ts`'s document-content mock so
 * `PdfRenderer` (real `pdf.js`) has real bytes to parse in dev/E2E, not a
 * fallback/placeholder image.
 */
function buildMinimalPdf(): Uint8Array {
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << >> >>',
  ];

  let body = '%PDF-1.4\n';
  const offsets: number[] = [0]; // object 0 is the free-list head, offset unused
  objects.forEach((content, index) => {
    offsets.push(body.length);
    body += `${String(index + 1)} 0 obj\n${content}\nendobj\n`;
  });

  const xrefOffset = body.length;
  const count = objects.length + 1;
  let xref = `xref\n0 ${String(count)}\n0000000000 65535 f \n`;
  for (const offset of offsets.slice(1)) {
    xref += `${offset.toString().padStart(10, '0')} 00000 n \n`;
  }

  const trailer = `trailer\n<< /Size ${String(count)} /Root 1 0 R >>\nstartxref\n${String(xrefOffset)}\n%%EOF`;

  return new TextEncoder().encode(body + xref + trailer);
}

export const MINIMAL_PDF_BYTES = buildMinimalPdf();
