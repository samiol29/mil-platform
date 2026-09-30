# ADR-008: Pipeline Idempotency and Exactly-Once Effects

**Status**: Accepted
**Date**: 2026-06-30
**Deciders**: Platform Architecture
**Context**: US2 Readiness Sprint — preparing the platform for the Intelligence Pipeline

---

## Context

ADR-007 establishes that cross-context domain events are delivered **at-least-once** through the Transactional Outbox and broker. The Intelligence Pipeline (US2) will consume these events in worker processes that pull jobs from the `JobQueue` and execute multi-step work: OCR, evidence extraction, and finding generation.

Two properties of the platform make at-least-once delivery dangerous if consumers are written naïvely:

1. **Evidence is append-only.** The data model forbids `UPDATE` and `DELETE` on `evidence.evidence_items`; corrections are made by supersession (a new row referencing the old). There is no overwrite path that could absorb a duplicate.
2. **The platform is a regulated audit product.** Duplicated evidence or findings are not a cosmetic defect — they corrupt the evidence chain, inflate findings, and undermine the reproducibility and defensibility guarantees of Principles II, VIII, and XII.

Therefore a redelivered event or a retried job must produce **exactly one** set of effects, not one set per delivery. This ADR records how the platform achieves exactly-once *effects* on top of at-least-once *delivery*.

This ADR documents the philosophy and the contract. It does not specify implementation; the work appears in the pre-US2 Architecture Readiness phase of `tasks.md`.

---

## Decision

**The platform assumes at-least-once delivery and achieves exactly-once effects at the consumer through deterministic idempotency keys, a per-job Unit of Work, and database-enforced uniqueness. Idempotency is a correctness requirement, not a best-effort optimisation.**

The decision has five parts.

### 1. At-least-once delivery is the assumption

Every consumer — every event subscriber and every job handler — is written on the assumption that it may receive the same logical message more than once. This can happen because:

- the outbox relay publishes a row, then fails before marking it published, and republishes on restart (ADR-007);
- a broker redelivers after a consumer acknowledgement is lost;
- a worker completes its side-effects, then crashes before acknowledging the job, so the job is redelivered;
- a retry policy re-enqueues a job after a transient failure.

Consumers MUST NOT assume exactly-once or at-most-once delivery from the transport.

### 2. Replay behaviour

A **replay** is the re-execution of a message whose effects have already been committed. The required behaviour of a replay is that it is a **no-op with respect to state**: it produces no new evidence, no new findings, no duplicate workflow steps, and no duplicate outbox events. A replay may safely re-acknowledge the message. Detecting a replay is the consumer's responsibility, performed via the idempotency key (part 3) backed by a unique constraint (part 5).

### 3. Deterministic idempotency keys

Each unit of work is identified by a **deterministic** key derived from stable inputs — never from a random value, a wall-clock timestamp, or an auto-generated id. The same logical work computes the same key on every delivery.

- **Jobs** carry a stable `idempotency_key` (the `Job` type already requires a non-empty key). For pipeline steps the key is derived from the work's identity — for example, from the workflow run and step rather than from the job's own random `job_id`.
- **Evidence creation** is keyed by the identity of the fact being recorded — derived from the source document, the extraction version that produced it, and the field's position/name — so that re-running extraction for the same document under the same extraction version cannot produce a second row for the same fact.
- **Finding generation** is keyed by the workflow run and the finding's logical identity, so that re-evaluating a submitted application does not create duplicate findings.

Because keys are deterministic, the *second* arrival of any message computes the *same* key as the first and is recognised as a replay.

### 4. Per-job Unit of Work

Each job handler executes within a **single database transaction** that encompasses all of its effects:

- the business write (e.g. the evidence rows, or the finding and its evidence snapshot);
- the workflow/step state update that records the step as complete (ADR-009);
- the outbox row(s) for any cross-context events the step emits (ADR-007).

These commit together or not at all. A worker crash between the side-effect and the acknowledgement therefore leaves the system in a clean prior state, and the redelivered job re-runs the whole unit — which the idempotency key then renders a no-op if a prior attempt had in fact committed. There is never a committed business write without its corresponding step state and outbox events, and never an acknowledged job with a half-applied effect.

### 5. Duplicate prevention via unique database constraints

Idempotency keys are enforced by **unique constraints in the database**, not only by application-level checks. Application checks (read-then-write) are subject to race conditions under concurrent workers; the unique constraint is the authority.

The consumer attempts its write; if the write violates the uniqueness constraint, the consumer treats the violation as proof that the work has already been done and converts it into a successful no-op (acknowledging the message). This makes duplicate prevention robust under concurrency and independent of delivery timing.

Append-only tables (evidence, snapshots) gain a unique constraint over their deterministic key so that the second insert fails fast rather than creating a duplicate row.

---

## Retry Philosophy

Retries exist to absorb **transient** failures, not to mask **terminal** ones.

- **Retryable vs. terminal classification is a property of the failure, declared at the source.** A provider that is momentarily unavailable (`PROVIDER_UNAVAILABLE`) is retryable; a structural failure such as a missing provider version (`PROVIDER_VERSION_MISSING`) or incomplete provenance (`EVIDENCE_PROVENANCE_INCOMPLETE`) is terminal and must not be retried. The classification belongs to the exception/error contract, not to a hard-coded list inside the orchestrator.
- **Retries are bounded.** The `Job` type carries `max_retries` and `retry_count`. Once retries are exhausted, the job is not silently dropped: it is routed to a dead-letter destination and a `WorkflowStepFailed` event is emitted so the failure is observable and auditable (Principles VIII and X).
- **Retries must back off.** A failing job must not be re-attempted in a tight loop. Retries use a delay/backoff so that a single poison message cannot starve the queue.
- **Retries are safe only because effects are idempotent.** The entire retry model depends on parts 3–5: re-running a step that partially or fully succeeded must not duplicate effects. Idempotency is what makes "just retry it" a correct strategy rather than a corrupting one.
- **Terminal failures are first-class outcomes.** A document that cannot be processed reaches a terminal failed state with an audit trail, rather than being retried indefinitely. Human-visible failure is preferable to silent corruption (Principle IV, Trust Before Automation).

---

## Consequences

### What this enables

- Safe at-least-once delivery: the platform can use a durable broker and tolerate redelivery, relay restarts, and worker crashes without producing duplicate evidence or findings.
- Concurrency safety: multiple worker replicas may process the queue simultaneously; uniqueness is enforced by the database, not by hopeful application logic.
- Reproducibility: because evidence and findings have deterministic identities, the same inputs produce the same records, supporting Principle XII.

### What this requires (pre-US2 Architecture Readiness phase; not in this ADR)

- Deterministic idempotency keys defined for pipeline jobs, evidence creation, and finding generation.
- Unique constraints over those keys in the relevant migrations.
- A per-job Unit of Work boundary in the worker execution path.
- A retry policy with classification, bounded attempts, backoff, and dead-letter routing.

### What this prohibits

- Consumers that assume a message is delivered exactly once.
- Idempotency keys derived from random ids or timestamps.
- Duplicate prevention by application-level read-then-write alone, without a backing unique constraint.
- Unbounded retries, tight-loop retries, or silent discarding of exhausted jobs.

### Interaction with the in-process implementations

`InProcessJobQueue` deduplicates by `idempotency_key` in memory and releases the key on acknowledgement. This is sufficient for single-process development and tests, but it is **not** the platform's idempotency guarantee. The durable guarantee is the database unique constraint (part 5), which holds across processes, restarts, and broker redelivery. US2 correctness must rest on the database constraint, not on the in-memory dedup set.

---

## Alternatives Considered

### Rely on the queue's in-memory idempotency only

Rejected. It does not survive process restart, does not coordinate across worker replicas, and provides no protection once a broker-backed queue replaces the in-process one. It is a development convenience, not a correctness mechanism.

### Make evidence mutable / upsert duplicates away

Rejected. It directly violates the append-only evidence model (ADR-006, data model) and the immutability guarantees that make the evidence chain legally defensible. Duplicates are prevented, not overwritten.

### Exactly-once delivery from the broker

Rejected as a foundation. True exactly-once delivery across a network is not achievable in general; brokers that advertise it do so within constrained conditions that the platform cannot assume across all deployment targets (including air-gapped ones). The platform achieves exactly-once *effects* at the consumer instead, which is portable and verifiable.

---

## References

- Engineering Constitution v1.1.0, Principle II (Evidence First)
- Engineering Constitution v1.1.0, Principle IV (Trust Before Automation)
- Engineering Constitution v1.1.0, Principle VIII (Auditability)
- Engineering Constitution v1.1.0, Principle XII (Deterministic Intelligence)
- ADR-006: Document Custody Model — immutable, append-only evidence foundation
- ADR-007: Transactional Outbox and Event Delivery Semantics — at-least-once delivery this ADR consumes
- ADR-009: Workflow Run and Version Pinning — workflow/step state written within the per-job Unit of Work
- `src/mil/kernel/job_queue.py` — `Job` idempotency key, `max_retries`/`retry_count`, in-process dedup
- `src/mil/kernel/errors.py` — `PROVIDER_UNAVAILABLE`, `PROVIDER_VERSION_MISSING`, `EVIDENCE_PROVENANCE_INCOMPLETE` codes
- Data model — append-only constraints on `evidence.evidence_items` and `evidence.evidence_snapshots`
