# ADR-009: Workflow Run, Version Pinning, and the Finding Generation Trigger

**Status**: Accepted
**Date**: 2026-06-30
**Deciders**: Platform Architecture
**Context**: US2 Readiness Sprint — preparing the platform for the Intelligence Pipeline

---

## Context

The Intelligence Orchestrator (US2) coordinates the multi-step pipeline that turns a stored document into structured evidence and, ultimately, into findings for human review. The orchestrator owns workflow state — `workflow_runs` and `workflow_steps` — and nothing else; it holds no business logic and no evidence or finding persistence.

The US2 Architecture Readiness Review identified three coordination decisions that must be settled before any orchestrator code is written, because they shape the orchestrator's data model and the events it emits:

1. **What a `WorkflowRun` is responsible for**, and in particular how the platform guarantees that a pipeline run produces reproducible, attributable output (Principle XII).
2. **How a single pipeline execution is correlated** end-to-end across events, jobs, and audit records, given that `correlation_id` exists on every `DomainEvent` but is currently never populated.
3. **When finding generation is triggered.** The plan's original flow generated findings per document, which cannot produce the cross-document findings that are the headline US2 capability.

This ADR records those decisions. It documents the contract; it specifies no implementation. The work appears in the pre-US2 Architecture Readiness phase and in US2 itself.

---

## Decision

### 1. WorkflowRun responsibilities

A `WorkflowRun` is the orchestrator's record of one execution of the intelligence pipeline. Its responsibilities are:

- **Coordinate, not compute.** It tracks the sequence and status of steps (`workflow_steps`). It does not perform OCR, extraction, evidence creation, or finding generation; those are executed by bounded-context services invoked from worker jobs.
- **Anchor reproducibility through version pinning** (part 2). The run is the single place that fixes the versioned configuration under which all of its steps execute.
- **Carry the correlation identity** (part 3) that threads the whole execution together for tracing and audit.
- **Own step lifecycle and failure outcome.** It records each step's progress and, on terminal failure, drives the run to a failed outcome with an emitted `WorkflowStepFailed` event. Step state is written inside the per-job Unit of Work defined in ADR-008.
- **Remain free of custody mutation.** The orchestrator does not write to `core.documents`. Where a document's `ingestion_status` must advance, it does so through the Document Processing service, preserving the custody boundary established in ADR-006.

### 2. Version pinning

Principle XII (Deterministic Intelligence) requires that every AI-generated finding be attributable to a specific model version, prompt version, policy version, and extraction version, and that identical inputs under identical versions yield reproducible output.

To guarantee this across a multi-step, asynchronous pipeline, **the versioned configuration is pinned on the `WorkflowRun` at the moment the run is created, and every step reads its versions from the run** — never from the live application record, the live provider registry, or the currently-active policy pack.

The pinned set comprises the platform's four attribution dimensions:

- **Policy version** — the Policy Pack active for the application at run start.
- **Model version** — the inference model version.
- **Prompt version** — the prompt template version.
- **Extraction version** — the extraction engine version.

Pinning makes the run immune to mid-flight configuration changes. If a Policy Pack is reactivated or a provider is upgraded while a run is in progress, that run continues under the versions it pinned; the change affects only subsequent runs. The pinned versions flow onto the evidence and findings the run produces, satisfying the attribution requirements of the data model and Principle XII. A later re-run under different versions is a new `WorkflowRun` with its own pinned set — which is exactly how the platform supports re-evaluating the same inputs under a new configuration without rewriting history.

### 3. Correlation IDs

Every `DomainEvent` already carries a `correlation_id` field; it is currently always empty. This ADR puts it to use.

- **A correlation id identifies one end-to-end pipeline execution.** It is established when the pipeline begins and is set to (or derived from) the `WorkflowRun` identity.
- **It propagates through everything the run touches**: the cross-context domain events the run emits (via the outbox, ADR-007), the jobs the run dispatches (`Job.payload`, ADR-008), and the audit events written by the steps (Principle VIII).
- **It enables single-trace reconstruction.** With a consistent correlation id, an operator or auditor can reconstruct the complete execution of a pipeline — upload through evidence through finding — from the events and audit records alone, satisfying the observability and reconstruction expectations of Principles X and VIII.

Correlation ids are for tracing and reconstruction. They are not idempotency keys (ADR-008) and not version attribution (part 2); those are separate concerns carried by separate fields.

### 4. Workflow lifecycle

A `WorkflowRun` progresses through an explicit lifecycle, with each significant transition observable as a domain event and recorded in audit:

- **Started** — the run is created, versions are pinned, the correlation id is established.
- **Step progression** — each step is dispatched, executed within its per-job Unit of Work, and recorded as completed or failed.
- **Completed** — all steps succeeded; the run reaches a successful terminal outcome.
- **Failed** — a step failed terminally (after the retry policy of ADR-008 is exhausted); the run reaches a failed terminal outcome and emits `WorkflowStepFailed`.

The lifecycle events that the plan promised but that do not yet exist in the kernel — workflow started, step completed, workflow completed — are introduced as typed domain events alongside the existing `WorkflowStepFailed`, so that pipeline progress is fully observable. Subscribers must not infer progress from delivery order; they read it from workflow state and lifecycle events.

### 5. Finding generation trigger

**Finding generation occurs after a `MortgageApplication` transitions to `SUBMITTED`. At that point the orchestrator evaluates all evidence for the application. Finding generation does NOT occur after each document.**

When an application is submitted, the orchestrator initiates finding generation over the **complete set of evidence** already extracted for that application. This is the only model that supports the cross-document findings that define US2 — for example, comparing income evidence across multiple documents for the same party to surface an inconsistency. A per-document trigger cannot see across documents and would emit premature or partial findings as each document finished extracting.

Consequences of this decision:

- **Document ingestion and finding generation are separate pipeline phases.** Document upload drives OCR and extraction (per document). Application submission drives finding generation (per application, over all evidence).
- **The trigger is the existing US1 lifecycle transition.** `MortgageApplication.submit()` (DRAFT → SUBMITTED) is the signal. The orchestrator reacts to the application's submission, not to individual document completion. This keeps a human-meaningful boundary — the reviewer decides the application is ready — consistent with Principle I (Human Decision Authority) and Principle IV (Trust Before Automation).
- **Submission presupposes extraction.** Evidence for the application's documents is expected to be available at submission. Handling of documents still mid-extraction at submission time (e.g. waiting, or generating against available evidence and re-running later) is an implementation concern for US2; the architectural decision fixed here is the trigger point and the application-wide evaluation scope.
- **A finding-generation run is itself a `WorkflowRun`** with its own pinned versions (part 2) and correlation id (part 3), distinct from the per-document ingestion runs.

---

## Consequences

### What this enables

- Reproducible, attributable findings (Principle XII), immune to mid-run configuration drift.
- Cross-document findings — the core US2 value — because evaluation is application-wide and triggered at a single, well-defined point.
- End-to-end traceability of any pipeline execution via correlation ids (Principles VIII, X).
- A clean separation between the orchestrator (coordination) and the bounded-context services (computation and persistence), preserving the boundaries in ARCHITECTURE.md and ADR-006.

### What this requires (pre-US2 Architecture Readiness phase and US2; not in this ADR)

- A `WorkflowRun`/`WorkflowStep` model that stores the pinned version set and the correlation id.
- Correlation-id propagation through outbox events, jobs, and audit events.
- New workflow lifecycle domain events (started, step completed, completed) alongside `WorkflowStepFailed`.
- An orchestrator subscription that initiates finding generation on application submission and evaluates all application evidence.

### What this prohibits

- Reading model/prompt/policy/extraction versions from live configuration during a run instead of from the run's pinned set.
- Generating findings per document.
- The orchestrator mutating `core.documents` directly (custody remains with Document Processing, ADR-006).
- Subscribers inferring pipeline progress from event delivery order rather than workflow state.

---

## Alternatives Considered

### Per-document finding generation (the plan's original flow)

Rejected. It cannot produce cross-document findings and emits premature, partial findings. It is the specific gap the readiness review flagged.

### Application-barrier trigger (generate when the Nth of N documents finishes extracting)

Rejected as the primary trigger. It depends on knowing the exact expected document count in advance, which is brittle (documents may be added or fail), and it removes the human-meaningful readiness boundary. Submission is a clearer, reviewer-owned signal. The barrier idea may inform how US2 ensures evidence is ready at submission, but it is not the trigger.

### Reading versions live instead of pinning

Rejected. It allows a policy or model change mid-run to split a single logical analysis across two configurations, breaking attribution and reproducibility (Principle XII).

### Reusing the idempotency key as the correlation id

Rejected. They answer different questions — "is this the same unit of work?" (idempotency, ADR-008) versus "which end-to-end execution does this belong to?" (correlation). Conflating them would weaken both.

---

## References

- Engineering Constitution v1.1.0, Principle I (Human Decision Authority)
- Engineering Constitution v1.1.0, Principle IV (Trust Before Automation)
- Engineering Constitution v1.1.0, Principle VIII (Auditability)
- Engineering Constitution v1.1.0, Principle X (Operational Excellence)
- Engineering Constitution v1.1.0, Principle XII (Deterministic Intelligence)
- ADR-006: Document Custody Model — custody boundary the orchestrator must not cross
- ADR-007: Transactional Outbox — channel for the workflow's cross-context events
- ADR-008: Pipeline Idempotency — per-job Unit of Work that writes workflow/step state
- `src/mil/kernel/events.py` — `DomainEvent.correlation_id`; existing `WorkflowStepFailed`; events to be added
- `src/mil/application/service.py` — `submit_application()` (DRAFT → SUBMITTED), the finding-generation trigger
- Data model — `findings` attribution fields; `workflow_runs` / `workflow_steps`; `evidence.evidence_snapshots`
