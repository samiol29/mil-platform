# ADR-010: Synchronous Cross-Context Read Access via Query Ports

**Status**: Accepted
**Date**: 2026-07-02
**Deciders**: Platform Architecture
**Context**: US2 Sprint 7 Readiness — preparing the platform for the AI Copilot bounded context

---

## Context

Every cross-context interaction the platform has built so far is **asynchronous and
write-oriented**: a context commits a state change, records a domain event in the
`outbox`, and a relay delivers it at-least-once to a subscriber that reacts by
producing *its own* state change (ADR-007, ADR-008). `ARCHITECTURE.md` §2 rule 4
codifies this as the sole channel:

> "Domain events defined in `mil/kernel/events.py` are the only cross-context
> communication channel. Bounded contexts must not call each other directly."

and §3:

> "They do not import each other's internal modules. Use events."

This rule is correct for **coordination** — it is what keeps OCR → Extraction →
Finding → Policy → Review decoupled and independently deployable. But the AI Copilot
(Sprint 7) introduces a fundamentally different interaction shape that the rule does
not cover: **synchronous, request-scoped, read-only aggregation across many contexts
at once.**

When a reviewer asks "explain why this Finding was generated," the Copilot must,
*inside a single HTTP request*, read the `MortgageApplication`, its `Document`s, the
`EvidenceItem`s, the `Finding`, the `PolicyResult`s for that finding, the
`ReviewSession` / `ReviewAction`s, and relevant `AuditEvent`s.

The events-only rule cannot serve this need for three structural reasons:

1. **Events are asynchronous and fire-and-forget.** They deliver a notification of a
   past fact to a subscriber that acts *later*. They cannot answer a question *now*;
   there is no request/response semantics in the outbox+relay model, by design.
2. **Events carry a snapshot at emission time, not the current queryable state.**
   Copilot needs whatever the current committed truth is at query time (e.g. the
   latest Review action), not a reconstruction from a historical event stream.
   Rebuilding a full read model purely from consumed events would mean every context
   re-persisting a shadow copy of every other context's data — enormous duplication,
   new consistency risks, and a violation of single-source-of-truth.
3. **The interaction is a pure read.** No state changes. None of the guarantees the
   events-only rule exists to protect (dual-write safety, at-least-once coordination,
   idempotent effects) are relevant to a read. Forcing reads through an asynchronous
   write-coordination channel imposes cost and complexity to guard against failure
   modes a read cannot cause.

The platform therefore needs a **sanctioned pattern for synchronous cross-context
reads** that does not reintroduce the direct coupling the events-only rule was written
to prevent. Building Copilot without recording this decision would either violate the
written architecture or smuggle in cross-context repository imports as an unexamined
precedent — neither acceptable in a regulated, audited platform.

---

## Decision

**The platform permits synchronous cross-context reads through consumer-defined Query
Ports. Writes and all state-changing coordination remain exclusively event/outbox-
driven. Query Ports are read-only interfaces, owned and declared by the *consuming*
context, and satisfied by adapters wired only in the composition root.**

> **Explicit constraint (non-negotiable):** Query Ports MUST NEVER be used for
> transactional business logic. They exist solely for synchronous read-side concerns
> such as explainability, reporting, and AI assistants. Any state change must continue
> to flow through domain services and Domain Events.

### 1. Two channels, two purposes

| Channel | Direction | Purpose | Coupling rule |
|---|---|---|---|
| **Domain events / outbox** (ADR-005/007/008) | Asynchronous, write-side | Cross-context **coordination**: one context's committed change triggers another's work | Producers know nothing of consumers; contexts never call each other |
| **Query Ports** (this ADR) | Synchronous, read-side | Cross-context **read/explainability**: one context assembles a view over others' current state | Consumer declares the interface it needs; producers know nothing of the consumer |

These are complementary, not competing. The events channel remains the *only* way one
context causes another to change. The Query Port channel is the *only* way one context
synchronously reads another. Neither permits a context to import another context's
internal service or model modules directly.

### 2. Consumer-defined interfaces (dependency inversion)

A Query Port is an **abstract read interface declared inside the consuming context**,
expressing exactly the reads that context needs — no more. The port is owned by the
**consumer**, not the producer. The producing context does not publish a "read API"
that consumers couple to; instead each consumer states the minimal read surface it
requires, and the producing context's existing persistence is *adapted* to satisfy it.
If two consumers need different read shapes over Findings, they declare two different
ports and the Finding context changes nothing.

### 3. Read-only by contract

A Query Port MUST expose only read operations. It MUST NOT expose any method that
mutates state, emits an event, or writes to the outbox. Returned data MUST be treated
as read-only by the consumer (detached read view objects, not live writable entities).
Enforcement is by contract and code review: a port with a write method is a defect.

### 4. Adapters live only in the composition root

The concrete objects that satisfy a Query Port — the **adapters** — are assembled
exclusively in the composition root (`container.py` / `api/deps.py`), never imported
into consumer code. An adapter wraps a producing context's existing read repository
and presents it through the consumer's port interface. The consumer's code depends
only on the abstract port; the wiring that connects it to the real repository is a
single composition-root concern. This preserves the platform's DI philosophy
(ARCHITECTURE §6), extending it from providers to cross-context reads.

### 5. Reads see committed truth, never partial writes

Query Ports read committed state. A consumer performing a read-only aggregation runs
in its own read transaction and never participates in a producing context's write
transaction. There is no dual-write, no shared unit of work across contexts for reads,
and therefore none of the ADR-007 safety machinery is required or permitted on this
channel.

---

## Why Query Ports preserve bounded contexts

- **No internal-module imports across contexts.** Consumer code imports only its own
  port abstractions. It never imports `mil.finding.models`, `mil.policy.service`, etc.
  The producing context's internals remain private.
- **The interface is owned by the side that has the need, not the side that has the
  data.** This Interface-Segregation + Dependency-Inversion combination keeps
  producers ignorant of consumers. The Finding context does not grow a "Copilot read
  API"; it stays unaware Copilot exists.
- **Service extraction remains a deployment change, not a rewrite** (ARCHITECTURE §1,
  §13). Because the consumer already talks to an abstraction, extracting a context into
  its own service later means replacing the local adapter with a remote (HTTP/gRPC)
  adapter in the composition root — the consumer's code is untouched.
- **The write-coordination discipline is untouched.** Nothing here lets a context
  *change* another's state synchronously. What the events-only rule protects — safe,
  idempotent, auditable state coordination — remains exactly as ADR-007/008 defined it.

---

## Dependency direction

```
   consumer.service ──depends-on──▶ consumer.ports.SomeReader   (abstraction, in consumer)
                                              ▲
                                              │ implements
                          consumer adapter (SomeReaderAdapter) ──wraps──▶ producing.Repository
                                              ▲
                                              │ constructed in
                                     composition root (container / deps)
```

Source-code dependency points *from the concrete adapter to the abstraction*, and from
the consumer's service to the abstraction — never from the consumer to the producing
context's internals. The only module that imports both the port and the producing
repository is the composition root.

---

## Composition-root responsibilities

1. Resolve each producing context's read repository for the current DB session.
2. Wrap each in its adapter, presenting the consumer's port interface.
3. Inject the port-typed adapters into the consumer (e.g. via a frozen collaborators
   dataclass, matching the existing worker composition pattern).
4. Ensure the consumer service only ever receives port-typed collaborators — never a
   concrete repository.

---

## Consequences

### What this enables
- The Copilot (and any future read-model, reporting, or analytics context) can
  synchronously assemble a cross-context view for explainability without duplicating
  data or violating boundaries.
- A clean, testable seam: ports are trivially faked in unit tests (the platform's
  established fake-collaborator pattern), so consumers are tested without any producing
  context present.
- A forward path to service extraction with no consumer rewrite.

### What this requires
- Consumers MUST declare their own read ports; they MUST NOT import producing contexts'
  internal modules.
- Adapters MUST be assembled only in the composition root.
- Ports MUST be read-only; any write remains on the events/outbox channel.
- `ARCHITECTURE.md` §2/§7 records the read-side exception explicitly (done alongside
  this ADR) so future contributors do not read the events-only rule as forbidding
  synchronous reads.

### What this prohibits
- Synchronous cross-context **writes** or state coordination (still events/outbox only).
- Using a Query Port for transactional business logic of any kind.
- A producing context publishing a shared "read service" that many consumers couple to
  directly (defeats consumer-owned interfaces).
- Consumers treating port-returned data as writable, or re-persisting it as a shadow
  source of truth.
- Bypassing ports by importing another context's repository/service into consumer code.

---

## Alternatives Considered

**A. Keep events-only; build an event-sourced read model in the consumer.** The
consumer would subscribe to every domain event and maintain its own materialized copy
of Application/Evidence/Finding/Policy/Review state. Rejected: massive data
duplication, a second source of truth for regulated data, new eventual-consistency
windows (Copilot could explain a stale Finding), and enormous complexity for what is
fundamentally a read. It also worsens the very auditability it would claim to serve.

**B. A shared "read facade" service in the kernel.** Put a god-object query service in
`mil/kernel/` that reads all contexts. Rejected: violates the domain-agnostic kernel
invariant (ARCHITECTURE §4, §12) — the kernel must not know about Findings or Policies
— and recreates central coupling.

**C. Producing contexts expose public read APIs that consumers import.** Each context
publishes its own `FindingQueryService`; consumers import them. Rejected: couples the
consumer to producer-owned interfaces (wrong ownership direction), leaks producer
internals into the consumer's dependency graph, and makes producers responsible for
consumer needs.

**D. Direct repository imports across contexts.** Simplest to write; the consumer
imports `finding.FindingRepository` directly. Rejected: exactly the internal-module
coupling ARCHITECTURE §3 forbids; binds the consumer to another context's persistence
details; blocks service extraction; untestable without the producing context.

---

## References
- Engineering Constitution v1.1.0 — Principle III (Explainability), Principle V
  (Auditability of data access), Principle IX (Incremental Evolution)
- ADR-005 — Domain Event Unification
- ADR-007 — Transactional Outbox (write-side coordination; unchanged by this ADR)
- ADR-008 — Pipeline Idempotency (applies to the write channel; reads are naturally
  idempotent)
- `ARCHITECTURE.md` §2 (dependency rules), §3 (bounded contexts), §6 (dependency
  injection), §7 (event-driven communication) — amended with the read-side exception
- ADR-011 — Grounded AI Copilot (first consumer of Query Ports)
- `src/mil/copilot/ports.py` — the first Query Port interfaces (read-only, consumer-owned)
