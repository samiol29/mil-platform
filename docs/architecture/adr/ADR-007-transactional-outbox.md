# ADR-007: Transactional Outbox and Event Delivery Semantics

**Status**: Accepted
**Date**: 2026-06-30
**Deciders**: Platform Architecture
**Context**: US2 Readiness Sprint — preparing the platform for the Intelligence Pipeline

---

## Context

US1 established the Application, Document, and Audit bounded contexts. The Document Processing context publishes a typed `DocumentIngested` domain event after a document is stored. US2 will introduce the first real cross-context subscriber to that event — the Intelligence Orchestrator — and will run that subscriber in a separate worker process backed by a message broker, as mandated by the implementation plan ("Asynchronous Job Processing Architecture", `mil-worker` containers).

The US2 Architecture Readiness Review identified that the current publication path is unsafe under this topology. This ADR records the decision to adopt a Transactional Outbox and to formally separate two distinct event-delivery semantics that the platform has, until now, treated informally.

### The current (unsafe) path

`DocumentService.ingest_document()` executes, in order:

1. `StorageProvider.store(content, content_hash)` — an external side-effect.
2. `repository.save(document, actor=user)` — flushes the `Document` row and its audit rows into the request's database session. **The commit happens later**, when the API `get_db` dependency returns.
3. `event_bus.publish(DocumentIngested(...))` — **before** that commit.

This is a **dual-write**: two independent systems (the database and the event bus/broker) are written in sequence with no shared transaction. Two failure modes follow directly:

- **Publish-before-commit, in-process bus.** With the synchronous `InProcessEventBus`, a US2 subscriber executes *inside the request, before the document row is committed*. It would create a `WorkflowRun` and dispatch jobs referencing a `document_id` that is not yet durable. If the request's commit subsequently fails or rolls back, the pipeline references a document that never existed. Conversely, an exception in the subscriber aborts an HTTP upload whose bytes are already stored.
- **Publish-before-commit, broker-backed bus.** With a broker and a separate worker process, the event can be delivered to the worker *before, or entirely without,* the database commit. The worker reads `core.documents` by id and finds nothing. The event and the row it describes have no atomic relationship.

The deferral recorded in ADR-005 ("Outbox pattern … Not needed while MIL is a modular monolith … Revisit if MIL is decomposed into separate services") rested on an assumption that is already false for US2: the plan's production topology is multi-process (API process + worker processes + broker). The outbox is needed now.

---

## Decision

**The platform adopts commit-before-publish for all cross-context domain events, implemented with a Transactional Outbox. The platform maintains two explicitly separate event-delivery channels with different guarantees.**

### 1. Commit-before-publish

A cross-context domain event must never be observable to any subscriber until the database transaction that produced the corresponding state change has committed. Publication is a consequence of commit, not a step that races it.

### 2. Transactional Outbox

The producing service writes the domain event as a row in an `outbox` table **within the same database transaction** as the business change. Because the business row and the outbox row commit (or roll back) together, the event is durably recorded if and only if the state change is durably recorded. There is no window in which one exists without the other.

### 3. Relay process

A separate relay reads committed, unpublished outbox rows and publishes them to the `EventBus` (broker), marking each row published once the broker has accepted it. The relay is the only component that publishes cross-context events to the broker.

### 4. Two delivery channels, two semantics

| Channel | What flows through it | When it is written | Delivery guarantee | Failure semantics |
|---|---|---|---|---|
| **Synchronous Audit** | `AuditEvent` records | In the same transaction as the domain change | Exactly-once with the transaction (atomic) | If the audit write fails, the domain change rolls back |
| **Asynchronous Domain Events** | `DomainEvent` (cross-context) | To the `outbox` table in the same transaction; relayed after commit | At-least-once (see ADR-008) | Relayed only after commit; redelivery possible; subscribers must be idempotent |

This separation is the central architectural point of this ADR.

---

## Audit Remains Synchronous and Transactional (Explicit Rejection)

The US2 Architecture Readiness Review raised, as one option, unifying audit and cross-context events behind a single subscriber model in which the audit writer becomes an asynchronous subscriber (the direction sketched in ADR-005's "Intended Future Design").

**This platform explicitly rejects making audit asynchronous.** Audit events MUST remain in the same database transaction as the domain change that produced them.

The rationale is rooted in the Engineering Constitution:

- **Principle VIII (Auditability)** requires that the audit history be complete and tamper-evident, and that audit events collectively support full reconstruction of an application's lifecycle. An asynchronous audit channel introduces a window in which a domain change is committed but its audit event is not yet written — a gap that is, by construction, indistinguishable from tampering. The `sequence_number` gap-detection mechanism in the audit schema depends on audit writes being atomic with the state changes they record.
- **Atomicity is the guarantee.** If a domain change commits, its audit record must already be committed with it. If the audit write fails, the domain change must roll back. This is only achievable when both writes share one transaction. The current `AuditWriter` design — writing `AuditEvent` rows into the caller's session, committed by the caller's unit of work — already provides exactly this and must be preserved.

Therefore:

- **Audit is synchronous and transactional.** It is not a subscriber. It is not relayed. It does not pass through the outbox.
- **Only cross-context `DomainEvent`s move through the Transactional Outbox.** These are the events that coordinate work between bounded contexts (e.g. `DocumentIngested`, and the US2 pipeline events).

The two mechanisms share a typed event vocabulary but deliberately do **not** share a delivery mechanism. This is now an explicit, binding architectural decision, superseding the "audit becomes a subscriber" step described in ADR-005's intended future design. ADR-005's broader move to typed `DomainEvent` objects for cross-context coordination still stands; only the audit-as-subscriber element is rejected.

---

## Event Delivery Guarantees

- **Outbox write**: atomic with the business change. An event is recorded if and only if its state change is committed.
- **Relay publication**: at-least-once. The relay may publish a row, fail before marking it published, and republish on restart. Subscribers therefore receive each event one or more times and MUST be idempotent. Exactly-once *effects* are achieved at the consumer through idempotency, not by the transport — see ADR-008.
- **Ordering**: not globally guaranteed across events. Subscribers must not depend on the relative order of distinct events. Where ordering matters, it is expressed through workflow state (ADR-009), not through delivery order.
- **Audit ordering**: the `audit.audit_events.sequence_number` provides a monotonic total order for audit reconstruction, independent of the outbox.

---

## Consequences

### What this enables

- The Intelligence Orchestrator (US2) can subscribe to `DocumentIngested` in a separate process with the guarantee that any document it observes is durably committed.
- The producing service no longer depends on subscriber behaviour for its own correctness; publication is decoupled from the request lifecycle, protecting interactive API latency targets.
- The platform's audit guarantees (Principle VIII) are strengthened, not weakened: audit remains atomic with domain changes while cross-context coordination becomes safely asynchronous.

### What this requires (implemented as the pre-US2 Architecture Readiness phase, not in this ADR)

- An `outbox` table and a producing-side write that participates in the domain transaction.
- A relay process that publishes committed outbox rows and records publication.
- Migration of cross-context publication (starting with `DocumentIngested`) from direct `event_bus.publish()` at the service layer to an outbox write inside the transaction.

### What this prohibits

- Publishing a cross-context domain event before the producing transaction has committed.
- Routing audit events through the outbox or any asynchronous channel.
- Subscribers assuming exactly-once delivery or cross-event ordering from the transport.

### Interaction with the in-process implementations

`InProcessEventBus` and `InProcessJobQueue` remain valid for development and tests, but US2 correctness MUST NOT depend on their synchronous, single-process behaviour. The outbox semantics are designed against the broker-backed, multi-process production topology; the in-process implementations are a convenience, not a correctness assumption.

---

## Alternatives Considered

### Keep publish-after-save without an outbox (status quo)

Rejected. It is a dual-write with no atomic relationship between the database and the broker. It is the precise failure this ADR exists to eliminate.

### Two-phase commit across database and broker

Rejected. Distributed transactions across a relational database and a message broker are operationally fragile, poorly supported across the broker implementations the platform targets, and contrary to the plan's stated avoidance of distributed-transaction complexity at the core of a regulated data product.

### Make audit an asynchronous subscriber (unify both channels)

Rejected explicitly, as documented above. It would introduce a commit-without-audit window incompatible with Principle VIII.

### Change Data Capture (CDC) on domain tables instead of an explicit outbox

Rejected for now. CDC couples event semantics to physical table structure and database-specific log shipping, weakening the bounded-context boundary and complicating air-gapped deployment. An explicit outbox table keeps the event contract in the domain and remains broker- and database-portable.

---

## References

- Engineering Constitution v1.1.0, Principle VIII (Auditability)
- Engineering Constitution v1.1.0, Principle X (Operational Excellence — observability/reconstruction)
- Engineering Constitution v1.1.0, Principle XII (Deterministic Intelligence)
- ADR-005: Domain Event Unification — supersedes the "audit becomes a subscriber" element of its intended future design
- ADR-008: Pipeline Idempotency and Exactly-Once Effects — consumer-side guarantees for at-least-once delivery
- ADR-009: Workflow Run and Version Pinning — workflow-driven ordering and the finding-generation trigger
- `src/mil/document/service.py` — current publish-after-save path to be migrated
- `src/mil/audit/writer.py` — synchronous, in-transaction audit writer (preserved unchanged)
- `src/mil/kernel/event_bus.py` — `EventBus` interface and in-process implementation
- Implementation Plan, "Asynchronous Job Processing Architecture" — broker-backed, multi-process topology
