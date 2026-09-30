# ADR-005: Domain Event Unification

**Status**: Accepted (Deferred until US2)
**Date**: 2026-06-30
**Deciders**: Platform Architecture
**Context**: Sprint 3B — Mortgage Application Domain

---

## Context

Sprint 3B introduced the `MortgageApplication` aggregate root and the `ApplicationRepository`. The aggregate must communicate state changes (application created, party added, status transitioned) to the rest of the platform so that the audit log, the Intelligence Orchestrator, operational metrics, and future notification systems can react to them.

Two broad approaches were considered:

**Option A — Lightweight dictionary events (current implementation)**
The aggregate appends plain `dict` objects to an internal `_pending_events` list. The repository drains the list after flushing the session and writes `AuditEvent` records directly via `AuditWriter`. No platform-level event infrastructure is required.

**Option B — Typed DomainEvent objects with a subscriber model**
The aggregate emits typed `DomainEvent` objects from a shared Platform Kernel hierarchy. The repository publishes them after flush. Audit, Intelligence Orchestrator, Metrics, and Notifications each subscribe independently.

---

## Decision

**Adopt Option A for Sprint 3B. Migrate to Option B before US2.**

Option A keeps Sprint 3B self-contained. The Intelligence Pipeline (Evidence Extraction, Findings, Intelligence Orchestrator) does not exist yet. Introducing a typed event hierarchy and subscriber infrastructure before there are real subscribers would be premature coupling — additional abstractions with no current consumers and no observable benefit.

The dictionary-based approach is intentional scaffolding, not a permanent design choice. It is replaced before any component that requires `DomainEvent` objects is built.

---

## Current Implementation (Sprint 3B)

### Event production

`MortgageApplication` appends lightweight dictionaries to `self._pending_events` on every state-changing method:

```python
self._pending_events.append({
    "event_type": "APPLICATION_CREATED",
    "entity_type": "APPLICATION",
    "entity_id": self.id,
    "data": {"status": ApplicationStatus.DRAFT, "los_reference": los_reference},
})
```

`collect_pending_events()` returns a copy of the list and clears the queue. The `@reconstructor` decorator re-initialises the list when SQLAlchemy loads an instance from the database (bypassing `__init__`).

### Event consumption

`ApplicationRepository.save()` implements the drain protocol:

1. Call `application.collect_pending_events()` — **before** `session.flush()` — to snapshot the queue.
2. Call `session.add(application)` and `session.flush()`.
3. For each collected event, call `AuditWriter.record(...)` in the **same session**, using the event dictionary fields as kwargs.

This guarantees atomicity: if the domain flush rolls back, the audit records roll back with it. If `AuditWriter.record()` fails, the domain flush also rolls back.

### Boundary

`AuditWriter` is the only consumer of pending events. It is the direct, synchronous consumer — not a subscriber. No other platform component reads these events at runtime in Sprint 3B.

---

## Motivation for Deferral

- The Intelligence Orchestrator, Document Processing, Evidence, Findings, Metrics, and Notification bounded contexts are not yet implemented. There are no additional consumers that need `DomainEvent` objects.
- Designing a subscriber protocol without real subscribers inverts the Engineering Constitution's Principle IX (Incremental Evolution): complexity added today would need to be maintained without producing any observable value.
- The dictionary representation is structurally equivalent to the typed representation for the single current consumer (`AuditWriter`). Migration cost is low and well-defined.
- Keeping the event format internal to the aggregate means the Platform Kernel event hierarchy can be designed with real consumer requirements in hand rather than speculative ones.

---

## Intended Future Design (before US2)

Before the Intelligence Pipeline begins, the following migration must be completed in a dedicated task. No US2 task may begin until this migration is done.

### 1. Platform Kernel DomainEvent hierarchy

Add to `mil/kernel/events.py` (or equivalent):

```python
@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    entity_type: str
    entity_id: UUID
    tenant_id: UUID
    occurred_at: datetime
    data: Mapping[str, object] = field(default_factory=dict)

class ApplicationCreated(DomainEvent): ...
class PartyAdded(DomainEvent): ...
class PartyRemoved(DomainEvent): ...
class ApplicationStateChanged(DomainEvent): ...
```

Typed subclasses make event structure explicit and allow subscribers to pattern-match on type rather than inspecting string keys.

### 2. Aggregate emits DomainEvent objects

`MortgageApplication._pending_events` changes from `list[dict]` to `list[DomainEvent]`. Each factory method and mutation method constructs the appropriate typed subclass.

### 3. Repository publishes DomainEvents

After `session.flush()`, `ApplicationRepository.save()` calls a `DomainEventPublisher` (or equivalent platform mechanism) with the collected events. The publisher dispatches to all registered subscribers in-process.

### 4. Audit becomes a subscriber

`AuditWriter` registers as a subscriber for all `DomainEvent` types relevant to the Application bounded context. It is no longer called directly by the repository. This removes the direct coupling between `ApplicationRepository` and `AuditWriter`.

### 5. Other subscribers join without modifying the aggregate or repository

The Intelligence Orchestrator, Metrics, and Notification components each register their own subscribers. The aggregate and repository remain unchanged as new consumers are added — the subscriber model provides the extension point.

---

## Consequences

### Immediate (Sprint 3B)

- No runtime behaviour changes.
- The dictionary-based event queue is an acknowledged transitional design. It is not to be extended with new fields or consumed by additional callers — that work belongs in the US2 migration task.
- `AuditWriter` remains the only direct consumer of `_pending_events`. No other code may call `collect_pending_events()` except `ApplicationRepository`.

### Before US2

- A dedicated migration task must convert `_pending_events` from `list[dict]` to `list[DomainEvent]`.
- `ApplicationRepository` must be updated to publish rather than drain-and-write directly.
- `AuditWriter` must be updated to subscribe rather than be called directly.
- All existing tests for the repository and audit writer must be updated to reflect the subscriber model.
- No US2 sprint task may begin until this migration task is complete and all tests pass.

### Long-term

- A single canonical `DomainEvent` type propagates through all platform components.
- New consumers (Intelligence Orchestrator, Metrics, Notifications) are added as subscribers without modifying the aggregate or repository.
- The audit log, event sourcing, and operational analytics share the same event stream.

---

## Alternatives Considered

### Immediate adoption of typed DomainEvent objects

Rejected for Sprint 3B. No consumers exist that require typed events. The subscriber infrastructure would add complexity with no observable benefit and no tests that verify real cross-component behaviour.

### SQLAlchemy event hooks (`@event.listens_for`)

Considered as an alternative drain mechanism. Rejected because SQLAlchemy hooks are harder to test in isolation, couple domain logic to the ORM lifecycle, and do not compose cleanly with a future publisher model.

### Outbox pattern (events written to a dedicated DB table, consumed by a poller)

Appropriate for eventual consistency across process boundaries. Not needed while MIL is a modular monolith. Revisit if MIL is decomposed into separate services.

---

## References

- Engineering Constitution v1.1.0, Principle VII (Domain-Driven Design)
- Engineering Constitution v1.1.0, Principle IX (Incremental Evolution)
- `src/mil/application/models.py` — `MortgageApplication.collect_pending_events()`
- `src/mil/application/repository.py` — `ApplicationRepository.save()`
- `src/mil/audit/writer.py` — `AuditWriter.record()`
