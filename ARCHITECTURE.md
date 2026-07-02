# MIL Platform Architecture

This document is the primary engineering handbook for contributors to the
Mortgage Intelligence Layer (MIL) platform.  Read it before adding a bounded
context, a provider, or a domain event.

---

## 1. Architecture Philosophy

MIL is built as a **Clean Architecture modular monolith**.  The monolith keeps
operational complexity low while the module boundaries enforce the same
discipline that microservices would — without the network and deployment
overhead of a distributed system.  Each bounded context is a self-contained
vertical slice.  Splitting a context into its own service at a later date
requires only a deployment change, not a code rewrite.

The platform is an **Intelligence Layer**, not a Loan Origination System.  It
reads from LOS platforms, enriches data with structured evidence and AI
findings, and returns results to the LOS.  It never approves or rejects loan
applications.  Human reviewers retain decision authority at every stage.

---

## 2. Clean Architecture Dependency Rules

```
          ┌─────────────────────────────────────┐
          │         Bounded Contexts             │
          │  (mortgage, document, evidence …)    │
          │                                      │
          │   ↓ depends on (inward only)         │
          ├─────────────────────────────────────┤
          │         Platform Kernel              │
          │  (mil/kernel/)                       │
          │                                      │
          │   ↓ depends on (standard library)    │
          └─────────────────────────────────────┘
```

**Rules — never violate these:**

1. Dependencies point inward.  `mil/kernel/` depends only on the Python
   standard library.  Bounded contexts depend on `mil/kernel/`.  Nothing in
   `mil/kernel/` imports from any bounded context package.
2. No circular dependencies anywhere in the codebase.
3. Concrete provider implementations (`src/providers/`) depend on
   `mil/kernel/providers/` but are never imported by `mil/kernel/` itself.
   They are wired together only in `container.py`.
4. Domain events defined in `mil/kernel/events.py` are the only cross-context
   channel for **writes and state-changing coordination**.  Bounded contexts
   must not call each other's services directly to change state, and must not
   import each other's internal modules.
   **Read-side exception (ADR-010):** synchronous, read-only cross-context
   access is permitted through **Query Ports** — consumer-owned, read-only
   interfaces satisfied by adapters wired only in the composition root.  Query
   Ports MUST NEVER be used for transactional business logic; they exist solely
   for synchronous read-side concerns such as explainability, reporting, and AI
   assistants.  Any state change must continue to flow through domain services
   and Domain Events.  See §7 and ADR-010.

---

## 3. Bounded Context Model

Each bounded context is a directory under `src/` (e.g. `src/mortgage/`,
`src/document/`, `src/evidence/`).  Contexts own their own:

- Domain models (entities, value objects)
- Application services (use-case orchestration)
- Repository interfaces (persistence contracts)
- FastAPI routers (HTTP delivery)

Contexts communicate by publishing and subscribing to domain events on the
`EventBus`.  They do not import each other's internal modules.

---

## 4. Platform Kernel Responsibilities

`mil/kernel/` is the only cross-cutting package imported by all bounded
contexts.  It provides:

| Module | Responsibility |
|---|---|
| `container.py` | Dependency injection container and factory |
| `config.py` | Settings loaded from environment variables |
| `errors.py` | Canonical error codes and exceptions |
| `events.py` | Frozen domain event dataclasses |
| `event_bus.py` | EventBus interface and in-process implementation |
| `job_queue.py` | JobQueue interface and in-process implementation |
| `observability.py` | Metrics, tracing, and structured logging primitives |
| `providers/` | Provider contracts and ProviderRegistry |
| `types.py` | Typed aliases (`TenantId`, `DocumentId`, etc.) |

The kernel must remain **completely domain-agnostic**.  Mortgage business
concepts belong in bounded contexts, not in the kernel.

---

## 5. Provider Framework Philosophy

Providers abstract every external system the platform depends on.  There are
five provider contracts defined in `mil/kernel/providers/`:

| Interface | Abstraction |
|---|---|
| `OCRProvider` | Converts document bytes into structured page text |
| `ExtractionProvider` | Extracts typed evidence from OCR output |
| `InferenceProvider` | Runs AI queries against a set of evidence |
| `StorageProvider` | Content-addressed blob storage |
| `LOSAdapter` | Reads application data from a Loan Origination System |

Concrete implementations live in `src/providers/`.  Development uses mock and
local-filesystem implementations.  Production swaps them for cloud-backed
implementations by updating the `register_*` calls in `_build_provider_registry()`.

Every provider method that produces an AI or ML output **must** return the
provider's version identifier as part of the response (Engineering Constitution
Principle XII — Deterministic Intelligence).

---

## 6. Dependency Injection Philosophy

`Container` (in `mil/kernel/container.py`) is a thin, type-safe DI registry.
There is a single container instance per application process, assembled once
during startup by `build_container()`.

**Bounded context services receive their dependencies through the container.**
They do not instantiate concrete classes directly.  Services resolve the
`ProviderRegistry` and call `get_ocr()`, `get_storage()`, etc. — they never
import `MockOCRProvider` or any other concrete class.

This one-directional wiring is what makes provider swaps transparent: replacing
`MockOCRProvider` with `AzureDocumentIntelligenceProvider` is a single line
change in `_build_provider_registry()`.

---

## 7. Event-Driven Communication Model

Bounded contexts communicate exclusively through domain events.

```
  Document Context            Evidence Context
       │                            │
       │  publishes                 │
       │  DocumentIngested ────────►│ subscribes
       │                            │
       │                            │  publishes
       │                            │  EvidenceExtracted ───► (next consumer)
```

Events are defined as frozen dataclasses in `mil/kernel/events.py`.
Handlers are registered on the `EventBus` at startup.
`InProcessEventBus` dispatches synchronously and is suitable for development
and test.  Production deployments register a broker-backed implementation
(e.g. Redis Streams, AMQP) that provides durability and fan-out.

**Event design rules:**

- Names are past-tense facts: `DocumentIngested`, not `IngestDocument`.
- Events carry all data subscribers need to act — no follow-up queries.
- Events record `tenant_id`, `event_id`, `occurred_at`, and `correlation_id`.
- Events are always serialisable to plain JSON.

### 7.1 Synchronous Read Access via Query Ports (ADR-010)

Domain events are the write-side coordination channel; they are asynchronous and
fire-and-forget, and cannot answer a synchronous, request-scoped question such as
"explain why this Finding was generated" (which must read Application, Documents,
Evidence, Findings, PolicyResults, Review history, and Audit *at once, now*).

For this **read-only** need, the platform sanctions **Query Ports** as an official,
narrowly-scoped exception to the events-only rule:

```
   consumer.service ──depends-on──▶ consumer.ports.SomeReader   (abstraction, in consumer)
                                              ▲  implements
                          consumer adapter (SomeReaderAdapter) ──wraps──▶ producing.Repository
                                              ▲  constructed in
                                     composition root (container / deps)
```

Rules:

- **Read-only, always.** A Query Port exposes only read methods.  It never mutates
  state, emits an event, or writes to the outbox.
- **Query Ports MUST NEVER be used for transactional business logic.** They exist
  solely for synchronous read-side concerns such as explainability, reporting, and AI
  assistants.  Any state change must continue to flow through domain services and
  Domain Events.
- **Consumer-owned.** The port interface is declared inside the *consuming* context,
  expressing exactly the reads it needs.  Producing contexts stay unaware of consumers.
- **No cross-context internal imports in consumer code.** The consumer depends only on
  its own port abstractions.  Adapters that wrap a producing context's read repository
  are constructed only in the composition root — never imported into consumer code.
- **Committed reads only.** A read-only aggregation runs in its own read transaction and
  never joins a producing context's write unit of work.

The first Query Ports are the Copilot read interfaces in `src/mil/copilot/ports.py`.

---

## 8. How to Add a New Bounded Context

1. Create `src/<context_name>/` with `__init__.py`.
2. Define domain models as dataclasses or Pydantic models inside the context.
3. Define repository interfaces (ABCs) inside the context — do not implement
   persistence in domain models.
4. Implement application services that orchestrate domain logic.
5. Add a FastAPI router in `src/<context_name>/api/`.
6. Register the router in `src/main.py`.
7. If the context needs a provider, resolve it through `ProviderRegistry` from
   the DI container — do not import concrete provider classes.
8. Never import from another bounded context's internal modules.  Use events.

---

## 9. How to Add a New Provider

1. If a new provider type is needed, define the abstract interface as a class
   in `src/mil/kernel/providers/<name>.py`.  Keep the interface small and
   cohesive — one capability, no business logic.
2. Add a `register_<name>` and `get_<name>` pair to `ProviderRegistry`.
3. Add the key to `_REQUIRED_PROVIDERS` only if every deployment must have it
   registered.  Optional integrations (like `LOSAdapter`) should not be in
   the required set.
4. Implement a development mock in `src/providers/<name>/mock_<name>.py`.
5. Write conformance tests in `tests/providers/test_<name>_conformance.py`
   covering: interface contract, version string, return type invariants, and
   field validation.
6. Register the mock in `_build_provider_registry()` in `container.py`.

---

## 10. How to Add a New Domain Event

1. Add a frozen dataclass to `src/mil/kernel/events.py` that extends
   `DomainEvent`.
2. Required positional fields go before the `KW_ONLY` sentinel inherited from
   `DomainEvent`.  Fields with defaults go after.
3. The event name must be a past-tense fact.
4. If the event relates to AI output, include a `*_version` field
   (e.g. `extraction_version`) to satisfy Principle XII.
5. Register a subscriber in the appropriate bounded context's startup hook.

---

## 11. Coding Conventions

- **Python 3.12+**.  Use `from __future__ import annotations` in every file.
- **ruff** for linting and formatting.  `make check` must pass before merging.
- **mypy strict** for type checking.  No untyped functions in `mil/kernel/`.
- **Frozen dataclasses** for all value objects, events, and immutable result
  types.  Mutable state belongs in services, not in domain objects.
- **`dataclasses.replace()`** for producing new versions of frozen objects
  (e.g. retry increment).
- **No comments that describe what code does** — only comments that explain
  *why* a design choice was made when it would otherwise be surprising.
- **No business logic in providers**.  Providers are I/O adapters only.
- **No concrete provider imports in bounded context code**.  Always resolve
  through the container.
- **Timezone-aware datetimes everywhere**.  Use `datetime.now(UTC)`.
- **SHA-256 content hashing** for all stored document bytes.

---

## 12. Common Architectural Anti-Patterns to Avoid

| Anti-pattern | Why it is wrong |
|---|---|
| Importing a concrete provider class in a bounded context | Breaks replaceability; couples the context to an implementation detail |
| Calling another bounded context's service directly to change state | Creates hidden coupling; use domain events instead. (Synchronous *read-only* access is allowed only through Query Ports — §7.1, ADR-010.) |
| Adding mortgage business logic to `mil/kernel/` | Violates the domain-agnostic kernel invariant |
| Storing credentials in source code or config files | Violates Engineering Constitution Principle V; use the secret management layer |
| Returning AI output without a version identifier | Violates Principle XII; every finding must be reproducible |
| Mutable domain events | Events represent immutable facts; mutation means the fact changed, which requires a new event |
| Skipping the `validate()` call on `ProviderRegistry` | Missing providers surface at first use, not at startup; always validate at boot |
| Using `InProcessJobQueue` or `InProcessEventBus` in production | These provide no durability; failing workers lose jobs silently |

---

## 13. Future Extension Philosophy

The Platform Kernel is **frozen**.  Future work should extend it rather than
restructure it.

Extensions follow this priority order:

1. **New bounded context** — add a context under `src/`; do not expand the
   kernel to accommodate it.
2. **New provider type** — add a kernel interface and a development mock;
   cloud implementations follow separately.
3. **New domain event** — add to `mil/kernel/events.py` following the
   existing conventions.
4. **New cross-cutting concern** — only additions to the kernel that are
   genuinely shared across every bounded context are justified.  When in
   doubt, put it in the bounded context.

The modular monolith structure means the first milestone of any future
service-extraction is a clean module boundary, not a rewrite.  Keep those
boundaries clean.

---

## 14. Production Hardening (US2 Sprint 8)

Every process (the API and each of the five pipeline workers) builds its own
DI container at startup via `build_container()`. Startup failures are
**explicit, not degraded operation** — a missing or duplicate provider
registration, or an invalid/placeholder production secret, raises during
startup and the process does not begin serving traffic or consuming jobs.

### 14.1 Operational endpoints

| Endpoint | Auth | Checks |
|---|---|---|
| `GET /v1/live` | None | Nothing — trivial process liveness |
| `GET /v1/health` | None | Version, uptime, static status |
| `GET /v1/ready` | None | Database connectivity, `ProviderRegistry.validate()`, applied-migration-matches-code-head |
| `GET /v1/metrics` | `read:operational` | In-process counters/histograms (see §14.2) |

`/v1/live` and `/v1/health` never touch the database or a provider — an
orchestrator's liveness probe must not depend on downstream infrastructure
being healthy. `/v1/ready` is the only probe that does, and is the correct
target for a readiness gate before routing traffic to a new instance.

### 14.2 Metrics

`mil.kernel.observability.MetricEmitter` (existing) is the platform's only
metrics abstraction — bounded contexts and workers depend on the interface,
never a concrete backend. `mil.kernel.metrics.InMemoryMetricEmitter` is the
default registered implementation: thread-safe in-process counters and
histograms (count/sum/min/max, not raw samples, so memory stays bounded),
exposed read-only via `GET /v1/metrics`. Swapping in a cross-process backend
(StatsD, CloudWatch, an OTel metrics exporter) is a single registration
change in `build_container` — no caller changes.

Named metrics (`mil.kernel.metrics.MetricName`): `http.requests.total`,
`http.request.duration_ms`, `copilot.requests.total`, `ocr.jobs.total`,
`workflow.executions.total`, `provider.failures.total`,
`audit.events.total`. This is explicitly **not** distributed tracing — no
spans are created; `TraceContext` in `observability.py` remains a dormant
primitive for a future OTel integration.

### 14.3 Structured logging

Every log record (`mil.kernel.observability.MILJsonFormatter`) carries
`timestamp`, `severity`, `service`, `component`, `request_id`,
`correlation_id`, `tenant_id`, `user_id`, and `event_type`. `request_id` /
`correlation_id` are bound per-request by `TelemetryMiddleware`
(`mil.api.middleware.telemetry`); `tenant_id` / `user_id` are merged in by
`get_current_user` once the caller is authenticated. Workers bind their own
`component` via `get_logger(__name__, component="...")`.

### 14.4 Security headers

`SecurityHeadersMiddleware` (`mil.api.middleware.security_headers`) adds
`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and
`Cache-Control: no-store` to every response, and
`Strict-Transport-Security` when the request arrived over HTTPS. This does
not change the authentication model (still bearer-token, `mil.api.deps`) —
it is response-header hardening only.

## 15. Backend Freeze Patch v1.0 (production-readiness guards)

The backend is feature-complete. This patch closes verified production risks
without redesigning any bounded context, provider, or ADR contract.

### 15.1 Authentication resolves through the DI container

`get_current_user` (`mil.api.deps`) no longer decodes bearer tokens with a
hard-coded, unsigned function. It resolves an `IdentityProvider`
(`mil.identity.provider`) from the DI container and delegates token
validation to it. Development registers `DevBearerIdentityProvider` — the
existing local development authentication (literal `dev` token and Base64URL
JSON tokens), unchanged. Staging/production require a signature-verifying
(e.g. OIDC/JWKS) `IdentityProvider`; none ships in this freeze, so a
non-development process **fails to start** rather than accept self-asserted
tokens (`main._register_identity_provider`).

### 15.2 Environment-selected providers, fail-fast in production

`build_container` (`mil.kernel.container`) selects providers by
`settings.mil_env`. Development registers the mock/local providers.
Staging/production wire real providers in `_register_production_providers`
(empty in this freeze). Two guards enforce the boundary:
`_reject_development_providers` refuses any `Mock*` / `LocalStorageProvider`
outside development, and `ProviderRegistry.validate()` refuses a process with
required providers missing. A production process therefore cannot start with
mock intelligence or ephemeral local storage.

### 15.3 Supported deployment model (honest topology)

Cross-process job/event delivery requires a broker-backed `JobQueue` /
`EventBus`; only the in-process implementations exist (ADR-007/008 always
scoped these as development-only). Until a broker implementation lands, the
**supported runnable topology is single-process development**. To make this
explicit rather than silently broken, `_reject_in_process_messaging` refuses
to start a non-development process wired with `InProcessJobQueue` /
`InProcessEventBus`. The multi-process API+workers topology remains the target
design (see `docs/deployment/README.md`); it is not runnable in this freeze.

### 15.4 Correlation-id propagation (pure ASGI middleware)

`TelemetryMiddleware` is now a pure-ASGI middleware. A `BaseHTTPMiddleware`
binds context variables in a task separate from the endpoint, so the
`request_id`/`correlation_id` did not reach handler/service logs. The ASGI
form binds the `LogContext` in the same task that awaits the downstream app,
so the correlation fields are visible to the handler (and to sync handlers
dispatched to the threadpool). Logging fields and header echo are unchanged.

### 15.5 Upload size limits

Document uploads are bounded by `MIL_MAX_UPLOAD_BYTES` (default 25 MiB).
`mil.api.v1.documents` reads the body in chunks and rejects an oversized
upload with HTTP 413 before the whole file is buffered, capping per-request
memory. Storage and custody (ADR-006) are unchanged.
