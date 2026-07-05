# MIL

## Mortgage Intelligence Platform

**Evidence-Driven Intelligence for Modern Mortgage Operations**

MIL enables financial institutions to transform fragmented mortgage documents into structured, explainable evidence while preserving complete human decision authority.

MIL provides a Mortgage Intelligence Layer that integrates with existing Loan Origination Systems to transform mortgage documents into structured, explainable evidence — enabling human reviewers to make informed lending decisions with confidence and complete auditability.

---

## The Mortgage Problem

Mortgage operations teams process large volumes of documents across every application: income statements, bank statements, property valuations, identity documents, employer letters, tax returns. Each document requires extraction, verification, and cross-referencing before a credit decision can be made.

The problems are well-known:

- **Evidence is fragmented.** Reviewers manually extract and compare data across dozens of documents for a single application, often without a structured view of what has been found or what is still missing.
- **Verification is inconsistent.** Cross-document checks — income against bank statements, declared employment against payslips — rely on individual reviewer discipline rather than systematic verification.
- **Findings lack traceability.** When decisions are challenged in audit or review, reconstructing the evidence trail is time-consuming and error-prone.
- **Operations are opaque.** Queue depth, reviewer workload, SLA compliance, and bottlenecks are visible only after the fact, when it is too late to intervene.

These are operational and governance problems. They exist independent of which LOS platform is in use.

---

## Why Existing LOS Platforms Need MIL

Loan Origination Systems manage the mortgage application lifecycle: intake, workflow routing, task assignment, and decision recording. They are not designed to be intelligence platforms.

MIL does not replace the LOS. It extends it.

The integration model is straightforward: MIL reads application and document data from the LOS, enriches it with structured evidence and explainable findings, and returns intelligence that reviewers can act on — all through the LOS interface they already use. No migration. No replacement. No disruption to existing workflows.

What MIL adds is the intelligence layer that LOS platforms were not built to provide: systematic evidence extraction, cross-document verification, finding explainability, human review workflows, and enterprise-grade audit trails.

---

## Business Outcomes

Financial institutions adopting MIL can expect measurable improvement across the mortgage review lifecycle.

**Operational efficiency** — Reviewers spend less time manually extracting and cross-referencing data across documents. Systematic evidence extraction reduces repetitive verification work that does not require human judgement.

**Reviewer consistency** — Cross-document verification is performed by the platform against an active policy configuration rather than relying on individual reviewer discipline. Reviewers act on structured findings rather than raw document content.

**Processing velocity** — Structured evidence and pre-generated findings are available to reviewers as soon as document ingestion is complete. Time spent reading and re-reading documents is reduced; time spent on decision-quality judgement is preserved.

**Audit readiness** — Every finding, every human action, and every policy evaluation is recorded in an immutable audit trail. When decisions are examined in internal audit or regulatory review, the full evidence chain can be reconstructed from the platform record without manual reconstruction from emails, spreadsheets, or LOS notes.

**Operational visibility** — Queue depth, SLA compliance, reviewer workload, and bottleneck indicators are available in real time rather than in retrospective reports. Operations teams can intervene before capacity issues become backlogs.

**Preserved accountability** — Human decision authority is enforced by the platform architecture, not by policy alone. No finding reaches a terminal state without an authenticated human action. Every override is recorded with a stated reason. Accountability remains unambiguously with the people making lending decisions.

**LOS continuity** — MIL connects to existing LOS platforms through documented adapter interfaces. There is no migration of application data, no replacement of existing workflows, and no requirement for mortgage professionals to change the tools they use.

---

## What MIL Is

MIL is an API-first Mortgage Intelligence Platform. It exposes a set of structured capabilities through versioned REST APIs that LOS platforms, review portals, and operational dashboards consume.

**MIL is not:**
- A Loan Origination System
- A Loan Decision Engine
- A Credit Scoring Engine
- A Fraud Decision Engine

MIL does not approve or reject mortgage applications. It does not replace human underwriters. Every lending decision remains with the people accountable for it.

**MIL does:**
- Extract and structure evidence from mortgage documents
- Verify consistency of evidence across documents and parties
- Generate explainable findings that reviewers can accept, verify, or override
- Record every human action and every AI output in an immutable audit trail
- Provide operational visibility into queue state, SLA compliance, and reviewer workload
- Integrate with existing LOS platforms through documented adapter interfaces

The platform identity is **Decision Assurance, not Decision Automation**.

---

## Core Platform Capabilities

### Document Intelligence
Ingests mortgage documents in supported formats and extracts structured evidence from each page. Every extracted evidence item retains full provenance: source document, page, location, extraction method, model version, and confidence score.

### Evidence Fabric
Maintains an immutable, append-only store of evidence items across all documents in an application. Corrections create new evidence items that reference what they supersede — the original extraction is always preserved. At the moment any finding is generated, the platform captures a point-in-time Evidence Snapshot to ensure findings remain reproducible for audit.

### Cross-Document Verification
Compares evidence items across documents and parties to identify inconsistencies — income declared in an application against income evidenced in payslips and bank statements, employment dates across multiple documents, property valuations against declared purchase price. Inconsistencies surface as structured findings for human review.

### Policy Engine
Evaluates evidence against versioned Policy Packs that define the institution's verification requirements. Policy Packs are configuration — they can be updated without platform releases. Every finding records which policy version produced it.

### Finding Engine
Generates structured findings from policy evaluation results. Every finding includes a title, rationale, evidence summary, confidence label, and recommended reviewer action. Every finding also records the model version, prompt version, policy version, and extraction version that produced it. None of these fields may be absent.

### Review Engine
Manages the full finding lifecycle: from extraction through human verification, override, escalation, and resolution. No finding can reach a terminal state without an authenticated human action. Override records capture the reviewer, the previous value, the new value, and the stated reason — all in the immutable audit trail.

### Evidence Copilot
An evidence-grounded query interface that allows reviewers to ask questions about an application in natural language and receive structured, cited responses. Responses are grounded in the application's own evidence — the Copilot does not draw on document content or data from other applications. Every response includes citations to the specific evidence items that support it.

### Operational Intelligence
Provides real-time visibility into review queue state, SLA compliance, turnaround times, reviewer workload distribution, and bottleneck indicators. Operational data is aggregate and updated on a configurable schedule. No application-level data is exposed in operational views.

### Integration Gateway
Manages bidirectional communication with LOS platforms through a standardised adapter interface. Inbound: reads application and document data from the LOS. Outbound: notifies the LOS of readiness status and finding summaries. The adapter interface is designed to support multiple LOS platforms without changes to the platform core.

---

## Example End-to-End Workflow

The following illustrates a typical document review lifecycle through MIL.

```
LOS Platform
    │
    │  Application submitted; documents available
    ▼
Integration Gateway
    │  Reads application and document references from LOS
    ▼
Document Intelligence
    │  Extracts structured evidence from each document
    │  Records provenance on every evidence item
    ▼
Evidence Fabric
    │  Stores evidence items (append-only)
    │  Captures Evidence Snapshot at finding time
    ▼
Policy Engine + Finding Engine
    │  Evaluates evidence against active Policy Pack
    │  Generates findings with full explainability and attribution
    ▼
Review Engine
    │  Findings enter NEEDS_REVIEW state
    │  Reviewer verifies, overrides, or escalates each finding
    │  Every action recorded in the Audit Trail
    ▼
Mortgage Readiness Assessment
    │  Platform reports readiness once all findings are resolved
    │  and all required evidence types are present
    ▼
Integration Gateway
    │  Notifies LOS of readiness status
    ▼
LOS Platform
       Underwriter proceeds with informed decision
```

The reviewer's LOS interface reflects finding status, evidence references, and readiness throughout. No LOS data is modified by MIL — the integration is read and notify only.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────┐
│               LOS Platform                  │
│   (NetOxygen · Encompass · Finastra · etc.) │
└───────────────────┬─────────────────────────┘
                    │  read · notify
                    ▼
┌─────────────────────────────────────────────┐
│            Integration Gateway              │
│   Inbound data · Outbound status dispatch   │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│        Mortgage Intelligence Platform       │
│                                             │
│  ┌──────────────┐   ┌─────────────────────┐ │
│  │ Platform Core│   │Intelligence         │ │
│  │ (Kernel)     │   │Orchestrator         │ │
│  └──────────────┘   └─────────────────────┘ │
│  ┌──────────────┐   ┌─────────────────────┐ │
│  │ Document     │   │Evidence Fabric      │ │
│  │ Intelligence │   │(append-only store)  │ │
│  └──────────────┘   └─────────────────────┘ │
│  ┌──────────────┐   ┌─────────────────────┐ │
│  │ Policy       │   │Finding Engine       │ │
│  │ Engine       │   │(explainability)     │ │
│  └──────────────┘   └─────────────────────┘ │
│  ┌──────────────┐   ┌─────────────────────┐ │
│  │ Review       │   │Evidence Copilot     │ │
│  │ Engine       │   │(grounded queries)   │ │
│  └──────────────┘   └─────────────────────┘ │
│  ┌──────────────┐   ┌─────────────────────┐ │
│  │ Operational  │   │Audit & Governance   │ │
│  │ Intelligence │   │(immutable trail)    │ │
│  └──────────────┘   └─────────────────────┘ │
└───────────────────┬─────────────────────────┘
                    │  Findings · Evidence · Readiness
                    ▼
┌─────────────────────────────────────────────┐
│        Human Mortgage Professionals         │
│  Verification Officers · Underwriters       │
│  Credit Analysts · Compliance · Audit       │
└─────────────────────────────────────────────┘
```

MIL is implemented as a modular monolith: a single deployable platform with strictly bounded internal modules. Module boundaries are enforced through explicit service interfaces rather than network calls. This architecture maintains strong consistency guarantees across the evidence chain — a requirement for regulated financial operations — while preserving the clean separation needed to extract individual modules to independent services as operational scale justifies it.

### Platform Components

| Component | Responsibility |
|---|---|
| **Platform Core** | Shared foundation: typed identifiers, event definitions, event bus and job queue abstractions, security primitives, observability, error contracts, dependency injection |
| **Intelligence Orchestrator** | Pipeline coordination: workflow state, step sequencing, retry handling, dead-letter management; translates domain events into background job dispatches |
| **Document Intelligence** | Document ingestion, OCR delegation, extraction pipeline execution, ingestion status lifecycle |
| **Evidence Fabric** | Evidence item storage (append-only), evidence relationships, evidence snapshots, provenance enforcement |
| **Policy Engine** | Policy Pack loading and versioning, rule evaluation against evidence, policy activation lifecycle |
| **Finding Engine** | Finding generation from policy evaluation, explainability field enforcement, attribution recording, finding lifecycle state machine |
| **Review Engine** | Verification, override, escalation, and resolution workflows; override record completeness enforcement |
| **Evidence Copilot** | Evidence-grounded query interface; application-scoped context assembly; citation extraction |
| **Operational Intelligence** | Queue snapshots, SLA evaluation, turnaround analytics, bottleneck indicators |
| **Integration Gateway** | LOS adapter interface; inbound webhook handling; outbound status dispatch; webhook delivery tracking |
| **Identity and Access** | Authentication, RBAC, ABAC, role assignment, cross-application access denial |
| **Audit and Governance** | Append-only audit event store (INSERT-only database permission); sequence number tamper detection; lifecycle reconstruction |

### Provider Interfaces

Five extension points allow the platform to remain vendor-agnostic:

- **OCRProvider** — document optical character recognition
- **ExtractionProvider** — structured evidence extraction from OCR output
- **InferenceProvider** — natural language inference for Evidence Copilot
- **StorageProvider** — document and artifact storage
- **LOSAdapter** — LOS platform integration (read, notify)

Concrete implementations are registered at deployment time. The platform core has no compile-time dependency on any specific implementation.

---

## Engineering Principles

These principles govern all platform decisions and may not be overridden by implementation convenience.

**Human Decision Authority** — The platform assists human decision makers. It does not approve or reject applications. Every lending decision remains with the people accountable for it.

**Evidence First** — Every conclusion must be backed by traceable evidence. Every extracted fact retains provenance. Documents are inputs. Evidence is the product.

**Explainability by Default** — Every finding must answer: what was found, why it was found, what evidence supports it, how confident the platform is, and what action the reviewer should take.

**Trust Before Automation** — The objective is not maximum automation. The objective is increasing confidence in human decisions through transparent and verifiable intelligence.

**Security and Privacy by Design** — Sensitive mortgage data is protected by design. The platform enforces least-privilege access, encryption, secure secret management, and data minimisation. AI context is scoped to the application being reviewed; evidence from other applications is never included.

**Auditability** — Every significant platform action and every human action is recorded in an immutable, append-only audit trail. Human overrides capture the reviewer identity, previous value, new value, and stated reason. The complete finding lifecycle can be reconstructed from the audit record alone.

**Deterministic Intelligence** — Every AI-generated finding is attributed to the exact model version, prompt version, policy version, extraction version, and timestamp that produced it. Findings are reproducible and attributable.

**Vendor Agnosticism** — The platform integrates with existing LOS platforms and does not lock institutions into specific AI vendors, OCR services, or cloud providers. All external integrations are behind versioned adapter interfaces.

**Regulatory Alignment** — Platform outputs are designed to support internal audit, regulatory examination, and governance requirements. Features that reduce explainability, traceability, or accountability are not introduced into the platform core.

---

## Current Project Status

**Phase**: Backend feature-complete and production-hardened (US2 Sprint 8)

The backend implements the full mortgage intelligence pipeline end to end —
Application/Document intake, OCR, Evidence Extraction, Finding Generation,
Policy Evaluation, Human Review, and the AI Copilot — behind a versioned REST
API, with health/readiness/liveness probes, basic platform metrics,
structured logging, and fail-fast startup validation. Frontend, LOS adapter
implementations, and notification channels are not yet built.

| Artifact / Milestone | Status |
|---|---|
| Engineering Constitution | Ratified v1.1.0 |
| Architecture Decision Records (ADR-005 – ADR-011) | Accepted |
| Platform Kernel, Provider Framework, Identity & Security | Implemented |
| Application, Document, OCR, Evidence, Finding, Policy, Review | Implemented |
| AI Copilot (foundation, inference, API integration) | Implemented |
| Production Hardening (health, metrics, logging, config validation, CI) | Implemented |
| Quality gates | ruff clean, mypy clean, `compileall` clean, unit + provider conformance suite passing |
| Frontend | Not started |
| LOS adapter implementations | Not started |

See `docs/deployment/README.md` for the startup sequence, environment
variables, and production checklist.

---

## Repository Structure

```
specs/
└── 001-mil-platform-spec/       # Platform specification artifacts
    ├── spec.md                  # Product Specification
    ├── plan.md                  # Architecture and Implementation Plan
    ├── research.md              # Architecture Decision Records
    ├── data-model.md            # PostgreSQL schema and entity model
    ├── tasks.md                 # Implementation task backlog
    ├── quickstart.md            # Validation scenarios and acceptance criteria
    └── checklists/
        └── requirements.md      # Specification quality checklist

.specify/
└── memory/
    └── constitution.md          # Engineering Constitution v1.1.0

docs/
├── adr/                          # Accepted Architecture Decision Records
└── deployment/                   # Deployment guide, production checklist

src/
├── main.py                       # ASGI entry point (uvicorn main:app)
├── mil/
│   ├── kernel/                   # Platform Core (shared foundation)
│   │   └── providers/            # Provider interface definitions
│   ├── orchestrator/              # Intelligence Orchestrator
│   ├── application/               # Application and Party management
│   ├── document/                  # Document Intelligence
│   ├── evidence/                  # Evidence Fabric
│   ├── policy/                    # Policy Engine
│   ├── finding/                    # Finding Engine
│   ├── review/                     # Review Engine
│   ├── copilot/                    # AI Copilot
│   ├── audit/                      # Audit and Governance
│   ├── identity/ (kernel.security) # RBAC/ABAC primitives
│   └── api/                        # REST API layer, schemas, middleware
├── workers/                       # Background pipeline workers (one per pipeline step)
└── providers/                     # Concrete provider implementations (mocks + local storage)

migrations/                       # Alembic database migrations
tests/
├── unit/                          # Unit tests (marked `unit`, no external dependencies)
├── integration/                   # Integration tests (require docker-up)
├── contract/                      # API contract tests
└── providers/                     # Provider conformance tests (marked `providers`)

Dockerfile                        # Production container image (API + all workers)
docker-compose.yml                # Local infrastructure (PostgreSQL, MinIO, Redis)
.github/workflows/ci.yml          # CI: ruff, format, mypy, pytest, compileall
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI |
| Data Layer | PostgreSQL, SQLAlchemy, Alembic |
| Validation | Pydantic |
| Observability | OpenTelemetry |
| Runtime | Python 3.12+ |
| Message Broker | Replaceable (Redis, AMQP-compatible, or equivalent) |
| Document Storage | Replaceable via StorageProvider interface |
| Intelligence Providers | Replaceable via provider interfaces (OCR, extraction, inference) |

The platform core has no hard dependency on any specific intelligence provider, cloud service, or message broker. Provider implementations are registered at deployment time.

---

## Getting Started

**Prerequisites**

- Python 3.12+
- Docker and Docker Compose

**Local development environment**

```bash
# Clone the repository
git clone <repository-url>
cd mivp

# Install dependencies (editable install, with dev/test extras)
make install-dev

# Start dependent services (PostgreSQL, MinIO, Redis)
make docker-up

# Apply database migrations
make migrate

# Start the API server (auto-reload)
make run-api

# In another terminal: start all five pipeline workers
make run-worker
```

Copy `.env.example` to `.env` and adjust before running — see
`docs/deployment/README.md` for the full environment variable reference.

**Validation**

```bash
make check   # ruff, ruff format --check, mypy
make test    # full pytest suite
make ci      # the complete CI gate: check + test + compileall
```

Once the API is running, `GET /v1/live`, `GET /v1/health`, and
`GET /v1/ready` confirm the process is up, healthy, and fully wired to its
dependencies (database, providers, migrations) respectively. See
`docs/deployment/README.md` for the full deployment flow and production
checklist, and `specs/001-mil-platform-spec/quickstart.md` for end-to-end
validation scenarios.

---

## Platform Vision

MIL is being engineered as a long-lived enterprise platform — one capable of supporting multiple financial institutions, evolving compliance frameworks, and future mortgage intelligence products without requiring changes to the platform's core principles or architecture. The bounded context structure, provider interfaces, Policy Pack model, and audit architecture are designed to accommodate new document types, new regulatory requirements, and new intelligence capabilities as extensions to the platform rather than revisions of it. The constitution, specification, and architecture decisions made at the outset are intended to remain authoritative as the platform matures.

---

## Development Roadmap

Implementation proceeds through five milestones. Each milestone is independently demonstrable before the next begins.

### Milestone 1 — Platform Foundation
Platform Core (kernel, providers, event bus, job queue), Identity and Access, Audit Trail, Application and Party management, Document upload. Deliverable: a secure, observable platform with complete audit trail and document ingestion capability.

### Milestone 2 — Mortgage Intelligence Core
Intelligence Orchestrator, Document Intelligence pipeline, Evidence Fabric, Policy Engine, Finding Engine. Deliverable: end-to-end document processing producing Evidence with full provenance and Findings with full explainability — the first enterprise MVP demonstration.

### Milestone 3 — Human Review
Review Engine, finding lifecycle (verify, override, escalate, resolve), Mortgage Readiness assessment. Deliverable: complete human verification workflow with audit trail on every action.

### Milestone 4 — Intelligence Workspace
Evidence Copilot, Operational Intelligence dashboards, queue monitoring, SLA compliance. Deliverable: reviewer query interface and real-time operational visibility.

### Milestone 5 — Enterprise Platform
LOS adapter implementations, multi-tenancy, data residency configuration, deployment hardening, compliance documentation, production readiness. Deliverable: platform ready for enterprise deployment across multiple financial institutions.

---

## Contributing

This repository is under active initial development. Contribution guidelines will be established at Milestone 1 completion.

All contributions must comply with the Engineering Constitution at `.specify/memory/constitution.md`. Pull requests that reduce explainability, auditability, or human decision authority will not be accepted regardless of implementation convenience.

---

## License

License to be determined. All rights reserved pending license selection.
