# MIL Platform — Deployment Guide

This document covers startup, environment configuration, deployment flow,
and the production readiness checklist. It complements `ARCHITECTURE.md`
(system design) and the root `README.md` (product overview).

---

## 1. Processes and supported deployment model

> **Supported deployment model (Backend Freeze Patch v1.0).** The
> multi-process topology below is the platform's **target** design. It
> requires a broker-backed `JobQueue` / `EventBus` so the API and worker
> processes can exchange jobs and events. Only the in-process (single-process,
> in-memory) implementations exist today; a broker-backed implementation is
> **not** part of this freeze. Accordingly, the platform is runnable and
> **supported only in development** (`MIL_ENV=development`, single process,
> in-memory queue/bus). A non-development process is **deliberately refused at
> startup** while it would be wired with development-only messaging or
> providers — see §6. Do not run this build as a distributed production
> deployment: the workers cannot receive jobs from the API until a broker
> `JobQueue`/`EventBus` is implemented and registered.

The platform is a modular monolith whose **target** topology runs as **six
independent processes**, all built from the same installed package:

| Process | Entry point | Role |
|---|---|---|
| API | `uvicorn main:app` | Serves all `/v1/*` HTTP routes |
| OCR worker | `python -m workers.document_pipeline` | OCR job pipeline step |
| Extraction worker | `python -m workers.extraction_pipeline` | Evidence extraction pipeline step |
| Finding worker | `python -m workers.finding_pipeline` | Finding generation pipeline step |
| Policy worker | `python -m workers.policy_pipeline` | Policy evaluation pipeline step |
| Review worker | `python -m workers.review_pipeline` | Human review handoff pipeline step |

All six read the same environment configuration (below) and connect to the
same PostgreSQL database, object store, and message broker. There is no
separate "worker image" — the Dockerfile at the repository root builds one
image; which process runs is just the container's command. **This topology is
not runnable until a broker-backed `JobQueue`/`EventBus` is added** (ADR-007/008
always scoped the in-process implementations as development-only).

---

## 2. Startup sequence

1. **Infrastructure first.** PostgreSQL, object storage (MinIO/S3), and the
   message broker (Redis or an AMQP-compatible broker) must be reachable
   before the API or any worker starts.
2. **Migrations.** Apply pending Alembic migrations (`alembic upgrade head`
   / `make migrate`) before starting the API or workers against a fresh or
   upgraded database. `GET /v1/ready` checks that the applied migration
   matches the code's expected head and reports `not_ready` (503) if not —
   this is a signal to run migrations, not a bug to route around.
3. **Start the API and workers.** Each process independently builds its own
   DI container at startup (`PlatformLifecycle` / `build_container`), which
   registers and validates all required providers
   (`ProviderRegistry.validate()`). **A process that cannot register every
   required provider (OCR, Extraction, Inference, Policy, Storage) fails to
   start — it does not start in a degraded state and silently misbehave
   later.** This is deliberate (Sprint 8 — Production Hardening: startup
   failures must be explicit).
4. **Confirm readiness.** Poll `GET /v1/ready` until it returns 200 before
   routing traffic to a new API instance (see §5).

Local development: `make docker-up && make migrate && make run-api` (and,
in another terminal, `make run-worker`).

---

## 3. Environment variables

All configuration is read from environment variables (see `.env.example`
for the full list with defaults). The canonical schema is
`src/mil/kernel/config.py` — `Settings` is a `pydantic-settings` model, so
an invalid or missing *typed* value (e.g. `MIL_PORT=not-a-number`) fails
application startup immediately with a clear validation error.

| Variable | Purpose | Required in production |
|---|---|---|
| `MIL_ENV` | `development` \| `staging` \| `production` | Yes |
| `MIL_LOG_LEVEL` | Root logger level | No (defaults to `INFO`) |
| `MIL_HOST` / `MIL_PORT` | API bind address | No |
| `MIL_SECRET_KEY` | Internal token signing secret | **Yes — see below** |
| `POSTGRES_HOST` / `PORT` / `DB` / `USER` / `PASSWORD` | Database connection | Yes |
| `STORAGE_ENDPOINT` / `ACCESS_KEY` / `SECRET_KEY` / `BUCKET` / `REGION` | Object storage | Yes |
| `REDIS_HOST` / `PORT` / `DB` / `PASSWORD` | Message broker | Yes |
| `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_SERVICE_NAME` | Observability export target | No |
| `WORKER_CONCURRENCY` / `WORKER_JOB_TIMEOUT` | Worker tuning | No |
| `MIL_MAX_UPLOAD_BYTES` | Max accepted document upload size (bytes) | No (defaults to 25 MiB) |

**Fail-fast guarantees enforced at startup** (`Settings` model validators,
`build_container`, and `ProviderRegistry.validate()`):

- `MIL_SECRET_KEY` and `POSTGRES_PASSWORD` **must not** be left at their
  placeholder default values when `MIL_ENV=production` — the process
  refuses to start (`ValueError` raised during settings construction).
- Every required provider (OCR, Extraction, Inference, Policy, Storage)
  must be registered exactly once — a missing provider raises
  `ProviderRegistryError` at startup; a duplicate registration (a
  configuration bug, not a runtime condition) also raises immediately.
- **(Backend Freeze Patch v1.0)** Outside development, `build_container`
  refuses to start a process that is wired with development-only providers
  (`Mock*`, `LocalStorageProvider`) or with the in-process `JobQueue`/
  `EventBus` (`ProductionReadinessError`), and the API refuses to start
  without a signature-verifying `IdentityProvider` registered. Because no
  production providers/IdP ship in this freeze, a non-development process
  fails fast by design — this is the honest signal that real providers, a
  real identity provider, and a broker-backed queue/bus must be wired before
  production use.

---

## 4. Health, readiness, and metrics endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /v1/live` | None | Trivial liveness — checks nothing but that the process can respond. Use as the container `HEALTHCHECK` / orchestrator liveness probe. |
| `GET /v1/health` | None | Process health: version, uptime, static status. Still no database/provider check. |
| `GET /v1/ready` | None | Deep dependency check: database connectivity, provider registration, migration state. Returns 503 (with per-check detail) if any check fails. Use as the orchestrator **readiness** probe — traffic should not be routed to an instance until this returns 200. |
| `GET /v1/metrics` | `read:operational` permission | In-process counters/histograms: HTTP requests, Copilot requests, OCR jobs, workflow executions, provider failures, audit events, average response time. Not a Prometheus exposition format — a plain JSON snapshot of the platform's own `MetricEmitter`. |

Kubernetes example:

```yaml
livenessProbe:
  httpGet: { path: /v1/live, port: 8000 }
  periodSeconds: 10
readinessProbe:
  httpGet: { path: /v1/ready, port: 8000 }
  periodSeconds: 10
  failureThreshold: 3
```

---

## 5. Deployment flow

1. Build the image: `docker build -t mil-platform:<tag> .`
2. Push to the target registry.
3. Run `alembic upgrade head` against the target database using the new
   image (`docker run ... mil-platform:<tag> alembic upgrade head`) —
   **before** rolling out new API/worker instances if the migration adds or
   changes anything the new code depends on.
4. Roll out new API instances behind the load balancer, gated on
   `GET /v1/ready` returning 200 (see health-check config above).
5. Roll out new worker instances. Workers have no HTTP surface; use process
   liveness (container restart policy) rather than an HTTP probe.
6. Confirm `GET /v1/metrics` (with an operator credential) shows request
   volume on the new instances before decommissioning the previous version.

This platform performs no autonomous LOS writes and no destructive
migrations are part of the normal flow — migrations in this codebase are
additive (see `migrations/versions/`). Any migration that is not purely
additive should be reviewed with the same care as a schema change in any
regulated system.

---

## 6. Production checklist

Before routing production traffic:

- [ ] `MIL_ENV=production` set, and `MIL_SECRET_KEY` / `POSTGRES_PASSWORD`
      are real, non-placeholder secrets from a secret manager (not committed
      to source, not in `.env` in the image).
- [ ] All five required providers (OCR, Extraction, Inference, Policy,
      Storage) are registered with production-grade implementations —
      `MockInferenceProvider` and the other `Mock*` providers under
      `src/providers/` are for development only and **must not** be
      registered in a production `build_container`.
- [ ] Database migrations applied (`alembic upgrade head`); `GET /v1/ready`
      reports `migration_state: ok`.
- [ ] TLS terminated in front of the API (the `Strict-Transport-Security`
      response header is only set when the request already arrived over
      HTTPS — see `mil.api.middleware.security_headers`).
- [ ] Structured JSON logs are being shipped somewhere queryable — every log
      line carries `request_id`, `correlation_id`, `tenant_id` (once
      authenticated), `component`, and `severity` (Sprint 8 logging
      requirement; see `mil.kernel.observability`).
- [ ] `GET /v1/metrics` is reachable only by operators with
      `read:operational` permission — it is not a public endpoint.
- [ ] `GET /v1/live` and `GET /v1/ready` wired into the orchestrator's
      liveness/readiness probes respectively (not the same probe for both).
- [ ] CI (`.github/workflows/ci.yml`) is green: ruff, ruff format, mypy,
      pytest (unit + provider conformance), and `compileall` all pass.
- [ ] Retention and access-control policy for the audit trail
      (`audit.audit_events`) is documented and enforced at the database
      level (INSERT-only application role — see `ARCHITECTURE.md` /
      migration `0001`).
- [ ] Backups configured for PostgreSQL and the object store, independent
      of this application.

---

## 7. Observability summary

- **Logging**: structured JSON via `mil.kernel.observability.configure_logging`
  (called once, in `main.lifespan`). Every record includes `timestamp`,
  `severity`, `service`, `component`, `request_id`, `correlation_id`,
  `tenant_id`, `user_id`, and `event_type`.
- **Metrics**: `mil.kernel.metrics.InMemoryMetricEmitter` is the default —
  in-process counters/histograms exposed at `GET /v1/metrics`. Swap in a
  different `MetricEmitter` implementation in `build_container` for
  cross-process aggregation (StatsD, CloudWatch, an OTel metrics exporter);
  callers never change, since they depend only on the `MetricEmitter`
  interface.
- **Tracing**: intentionally out of scope for this hardening pass — the
  platform does not implement distributed tracing. `mil.kernel.observability`
  retains a `TraceContext` primitive for future OpenTelemetry span
  propagation if that is added later; nothing wires it today.
