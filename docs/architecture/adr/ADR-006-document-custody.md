# ADR-006: Document Custody Model

**Status**: Accepted
**Date**: 2026-06-30
**Deciders**: Platform Architecture
**Context**: Sprint 3C — Document Processing Bounded Context

---

## Context

The Document Processing bounded context (Sprint 3C) introduces the `Document` entity as a first-class platform asset. A document is a source file submitted by a mortgage applicant as part of an application — payslips, bank statements, tax returns, identity documents, and similar.

The platform must be able to answer two questions with certainty at any point in the mortgage lifecycle:

> "Exactly which file was uploaded?"
> "Can we prove this is the same file that produced this evidence?"

These questions have legal and regulatory weight. If evidence extracted by the Intelligence Pipeline (US2) is ever disputed — by an applicant, an auditor, or a regulator — the platform must be able to reconstruct an unbroken chain of custody from original bytes to extracted fact.

This ADR establishes the custody model that makes that guarantee possible and documents why each design constraint is non-negotiable.

---

## Decision

**The Document entity and its associated identifiers are permanently immutable after the upload transaction commits.**

The following specific rules are derived from this principle and are binding on all current and future bounded contexts:

1. `Document.content_hash` (SHA-256 hex digest) is computed exactly once during ingestion and never changes.
2. `Document.storage_reference` is set once when the file is written to durable storage and never changes.
3. `Document.original_filename` is display metadata only. No business logic, routing, deduplication, or downstream processing may depend on it.
4. `Document.id` is the canonical identity for every downstream reference to a document.
5. The OCR, Evidence, Findings, and Intelligence Orchestrator bounded contexts are read-only consumers of `Document`. They must never update any field on a `Document` record.
6. Downstream bounded contexts reference documents exclusively via `Document.id`. They must not store or operate on filenames, storage paths, or content bytes directly.
7. `IngestionStatus` is the only mutable field on `Document` after the upload transaction commits, and only the Intelligence Pipeline (US2) may advance it.

---

## Why Documents Are Immutable

### Legal chain of custody

Mortgage documents are legal instruments. A bank statement, payslip, or tax return submitted as part of a credit application must remain unchanged for the full audit and retention period (commonly 7–10 years in regulated jurisdictions). If the platform allowed a document record to be modified after upload, the platform could not assert that the evidence it produced came from the file the applicant actually submitted.

Immutability is not a performance optimisation or a simplification. It is the property that makes the platform's outputs legally defensible.

### Reproducibility of intelligence outputs

The Intelligence Pipeline will extract structured evidence from documents: income figures, employment tenure, account balances, property valuations. Reviewers and auditors will challenge those findings. The platform must be able to re-run extraction against the exact byte sequence that was processed at the time of the original analysis. If the document is mutable, re-processing cannot be guaranteed to produce the same result, and the platform's outputs become legally unreliable.

Immutability guarantees that `content_hash` + `storage_reference` always refers to the same bytes, regardless of when the retrieval happens.

---

## Why Filenames Are Metadata Only

### Filenames are applicant-controlled strings

A file named `bank_statement.pdf` may contain payslip data, fabricated figures, or an unrelated document. Conversely, a file named `IMG_20260601_133742.jpg` may contain a valid bank statement. The platform cannot infer document type, authenticity, or relevance from the filename.

Routing, classification, extraction, and verification must be based on document content — not on the name chosen by the applicant or the system that submitted the file. Any platform component that makes a business decision based on `original_filename` introduces a bypass of the content-based intelligence pipeline, creating both a security surface and a source of undetectable errors.

`original_filename` is preserved because users and reviewers need a human-readable label. It is presented in the UI as display metadata alongside the document type classification produced by the Intelligence Pipeline. It must never appear in routing logic, extraction triggers, or downstream queries.

### Filename collisions and conflicts

Multiple documents with identical filenames are valid and common: two co-applicants may each upload a file called `payslip.pdf`. If downstream processing used filenames as identifiers, these documents would be indistinguishable. `Document.id` is unique per upload and is the only safe discriminator.

---

## Why SHA-256 Provides Integrity

### Content addressing

SHA-256 maps any byte sequence to a unique 64-character hex digest with negligible collision probability. If the stored bytes are identical to the originally uploaded bytes, the SHA-256 digests will be identical. If even a single bit differs — through data corruption, deliberate tampering, or storage failure — the digests will differ.

`StorageProvider.verify_integrity(reference, expected_hash)` uses this property to detect corruption at retrieval time. The `DocumentService` and any future retrieval path can confirm, without accessing any other metadata, that the file returned from storage is identical to the file that was uploaded.

### Deduplication without content inspection

If two uploads produce the same `content_hash`, the files are byte-for-byte identical. The platform can use this for deduplication in storage (content-addressed storage writes are idempotent) without reading or comparing the file contents at deduplication time. The hash is a safe, opaque fingerprint that supports deduplication without exposing file contents.

### Tamper evidence

The `content_hash` stored in `core.documents` is computed before the file is handed to `StorageProvider`. If `storage_reference` later retrieves different bytes, the mismatch between the stored hash and the recomputed hash constitutes tamper evidence. This is the platform's primary defence against storage-layer corruption or interference.

### Single computation, single source of truth

`DocumentService.ingest_document()` computes `content_hash` exactly once from the raw uploaded bytes, using `hashlib.sha256(content).hexdigest()`. This value is passed to both `StorageProvider.store()` and `Document.create()`. It is never recomputed from stored bytes, never recomputed by a downstream consumer, and never overwritten. The `core.documents` table record is the authoritative source of truth for the hash.

---

## Why StorageReference Is Immutable

`StorageReference` is a content-addressed pointer: the path in object storage where the file lives. Because storage is content-addressed (files are keyed by their SHA-256 hash), a given `content_hash` maps to a stable, permanent location. There is never a valid reason to change the location of a file after it is stored — if the storage backend is migrated, the migration is a platform infrastructure operation that must preserve the relationship between `Document.id`, `content_hash`, and the new `storage_reference`. It is never a document-level update.

Allowing `storage_reference` to change after ingestion would break the chain of custody: the platform could no longer assert that the bytes at the reference correspond to the original upload.

---

## Why Document.id Is the Canonical Identity

### Immutable handle

`Document.id` (a UUID generated once at `Document.create()`) is the stable, opaque handle by which every platform component and every external API consumer refers to a specific document. It never changes. It does not encode content, type, or position. It is unambiguous.

### Alternative identifiers are insufficient

`content_hash` is not a safe identity for a document because two distinct uploads (from different applicants, at different times, for different applications) may produce identical hashes if the files are identical. The hash identifies the file content, not the upload event. A payslip template used by thousands of applicants would produce the same hash for every upload.

`storage_reference` is not a safe identity because content-addressed storage may deduplicate at the storage layer, making multiple `Document` records share a single storage path. The reference identifies the storage location, not the submission.

`original_filename` is not a safe identity for reasons already stated.

`Document.id` is the only identifier that is unique per upload event, stable across the document lifecycle, and opaque to content — making it the correct identity for all inter-context references and all external API surfaces.

---

## Why Downstream Bounded Contexts Are Read-Only Consumers

### Separation of custody and intelligence

The Document Processing bounded context is responsible for custody: accepting uploads, storing bytes, and establishing the immutable record. The Intelligence Pipeline (OCR, Evidence, Findings, Intelligence Orchestrator) is responsible for understanding: reading bytes, extracting structured data, and deriving evidence.

These are distinct responsibilities and must remain separate. Intelligence components must never write to `core.documents`. They produce their own records in their own schemas (`evidence.evidence_items`, `evidence.findings`, etc.) that reference documents by `Document.id`. Upstream custody records are never modified by downstream intelligence.

This separation has three consequences:

1. Intelligence can fail, retry, or produce wrong results without corrupting the document record.
2. The document record can be re-processed by a newer or different intelligence model without the original custody facts changing.
3. A regulatory audit can independently verify: "This document was submitted on date X by user Y, has this hash, lives at this reference, and these evidence items were extracted from it by this pipeline run."

### IngestionStatus is the only permitted mutation

`IngestionStatus` is the single exception: the Intelligence Pipeline is authorised to advance the document's processing state (`PENDING → IN_PROGRESS → COMPLETED | FAILED`). This is not a mutation of the custody facts — it is a reflection of pipeline progress. The content, hash, reference, filename, and identity are unaffected by status transitions.

---

## How Downstream Bounded Contexts Reference Documents

Downstream contexts must follow this pattern:

```
evidence.evidence_items.document_id  →  core.documents.id
evidence.findings.document_id        →  core.documents.id
```

A downstream context that needs to retrieve or display a document calls the Document API (or `DocumentService.get_document()`) using the stored `document_id`. It must not cache or copy `storage_reference`, `content_hash`, or `original_filename` into its own schema for business purposes — those fields must always be read from the authoritative source in `core.documents`.

Cross-context joins on `document_id` are permitted for read queries. No cross-context write to `core.documents` is permitted.

The `DocumentIngested` domain event (published on the `EventBus` after a successful upload) carries `document_id`, `content_hash`, and `storage_reference` as initial context. Downstream subscribers may use these fields to begin processing but must treat `core.documents` as the authoritative record and must not persist copies of these fields as mutable state.

---

## Consequences

### What this enables

- Legal defensibility: the platform can reconstruct the exact file submitted at any point in the document's life.
- Intelligence reproducibility: any extraction or analysis can be re-run against the same byte sequence.
- Tamper evidence: hash mismatches at retrieval time surface storage corruption immediately.
- Independent intelligence retries: a failed or improved pipeline run processes the same document without touching the custody record.
- Clean audit trail: every access, every processing event, and every status change is associated with an immutable document identity.

### What this prohibits

- Updating `content_hash`, `storage_reference`, `original_filename`, `uploaded_by`, or `uploaded_at` after the upload transaction commits. These fields must have no update path in the repository.
- Business logic that branches on `original_filename`. Such logic must be rejected at code review.
- Downstream bounded contexts writing to `core.documents` for any reason other than `IngestionStatus` advancement.
- Storing `storage_reference` or `content_hash` in a downstream schema as mutable state. They may be denormalised for read performance only, and the copy must never diverge from the authoritative record.

### Impact on future development

Every new bounded context or feature that touches documents must be reviewed against this ADR. Any proposed modification to `core.documents` fields (other than `ingestion_status`) requires a new ADR and explicit architectural justification.

---

## Alternatives Considered

### Mutable documents with version history

Some document management systems allow documents to be replaced or versioned: a user uploads a corrected statement and the system retains both the old and new versions. This approach was rejected because it increases the complexity of the chain-of-custody model significantly: every piece of evidence must record which version of the document it was extracted from, and every query must specify which version is canonical. The incremental complexity outweighs the benefit for a platform whose primary purpose is decision assurance, not document management.

### Using content_hash as the document identifier

Rejected. Identical file content from different submissions must produce distinct document records. The hash identifies the bytes; the `Document.id` identifies the upload event. Collapsing these would make it impossible to track which applicant submitted which file independently.

### Allowing filenames in routing

Rejected unconditionally. Filename-based routing has been the source of data quality failures in document processing systems across the financial services industry. The Engineering Constitution's Evidence First principle requires that conclusions be based on document content, not on metadata provided by the submitter.

---

## References

- Engineering Constitution v1.1.0, Principle II (Evidence First)
- Engineering Constitution v1.1.0, Principle VII (Domain-Driven Design)
- Engineering Constitution v1.1.0, Principle VIII (Auditability)
- Engineering Constitution v1.1.0, Principle XI (Regulatory Alignment)
- ADR-005: Domain Event Unification — dict-based pending event pattern used by Document
- `src/mil/document/models.py` — `Document.create()`, immutable field assignment
- `src/mil/document/repository.py` — `DocumentRepository.save()`, no update path for custody fields
- `src/mil/document/service.py` — `DocumentService.ingest_document()`, single SHA-256 computation
- `src/mil/kernel/providers/storage.py` — `StorageProvider.verify_integrity()`
- `src/mil/kernel/events.py` — `DocumentIngested` domain event
- `migrations/versions/0002_document_context.py` — `core.documents` schema
