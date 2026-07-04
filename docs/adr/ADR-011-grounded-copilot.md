# ADR-011: Grounded AI Copilot

**Status**: Accepted
**Date**: 2026-07-02
**Deciders**: Platform Architecture
**Context**: US2 Sprint 7 — the AI Copilot bounded context

---

## Context

The platform is feature-complete through Human Review. The next capability is an **AI
Copilot** that assists mortgage officers with explainability and productivity:
explaining Findings and Policy results, summarizing applications, answering
natural-language questions, recommending missing documents, highlighting
inconsistencies, suggesting next reviewer actions, and searching an application's
history.

This capability sits at the exact center of the Engineering Constitution's most
sensitive tensions: it is an AI surface (Principle I — Human Decision Authority;
Principle IV — Trust Before Automation), it handles the most sensitive personal
financial data (Principle V), and its entire value is explainability (Principle III)
under audit (Principles VIII, XII). A Copilot designed carelessly could become a shadow
decision-maker, a data-leak vector, or a source of unattributable, unciteable claims —
each architecturally incompatible with a regulated mortgage platform.

This ADR fixes the Copilot's responsibilities, guarantees, and constraints **before**
implementation, so the boundaries are architectural facts rather than implementation
choices. It does not implement the Copilot.

---

## Decision

**The Copilot is a read-only, evidence-grounded, fully-attributed explainability
assistant. It has no decision authority, no write path, and no capacity to answer
beyond cited, application-scoped governed data. These properties are guaranteed
structurally — by what the bounded context is allowed to depend on — not merely by
prompt instructions.**

### 1. Responsibilities

- Assemble an application-scoped, permission-scoped **grounding set** from governed
  data (Evidence, Findings, PolicyResults, Review actions, Documents, Audit) via
  read-only Query Ports (ADR-010).
- Delegate natural-language generation to the `InferenceProvider` with a **pinned
  prompt version**.
- **Validate every citation** in the response against the grounding set before
  returning it.
- Persist conversations, messages, citations, and grounding snapshots as immutable,
  append-only records (Sprint 7).
- Emit synchronous audit events for every query and response (data-access logging).

### 2. Non-responsibilities (hard prohibitions)

The Copilot MUST NEVER:
- approve or reject applications;
- mutate a Finding, PolicyResult, ReviewSession, ReviewAction, Evidence, or Document;
- override a reviewer or emit any event that causes another context to change state;
- perform or expose hidden reasoning presented as fact;
- retain or use memory across conversations or across applications;
- answer from parametric/model knowledge rather than from the grounding set.

These are enforced by construction: the Copilot package depends **only** on read-only
Query Ports and the `InferenceProvider`. No write repository, no outbox producer for
state changes, and no service of Finding/Policy/Review is present in its dependency
graph. It *cannot* mutate a decision even if instructed to — there is no code path.

### 3. Read-only guarantee

All cross-context access is through the read-only Query Ports of ADR-010. Copilot runs
in a read transaction, never participates in another context's write unit of work, and
treats all retrieved data as immutable read views. The only tables Copilot writes are
its own (`copilot` schema, Sprint 7) plus synchronous audit rows. It writes nothing in
any other context's schema.

### 4. Explainability (Principle III)

Every Copilot response must be capable of answering, in reviewer-interpretable terms:
**What** was found, **Why**, **What evidence** supports it, **How confident** and its
limits, and **What action** the reviewer might consider. Responses that cannot satisfy
this — because grounding data is absent — MUST degrade to an explicit "insufficient
evidence" answer rather than fabricating one. Suggested actions are always advisory
("consider verifying…"), never directives, preserving Principle I.

### 5. Grounding

Copilot answers **only** from a retrieved grounding set scoped to a single
`application_id` and `tenant_id`. Grounding is deterministic structured retrieval over
governed records (Phase 1); free-text/vector retrieval is deferred and, when added,
MUST be partitioned per application. The grounding set is minimized to what the query's
intent requires (least-data, §9). The exact grounding set and the versions of its
sources are captured in an immutable **grounding snapshot** per response.

### 6. Citations

Every substantive claim in a response MUST cite a governed record: an `evidence_ref`,
`finding_id`, `policy_result_id`, `review_action_id`, `document_id`, or
`audit_event_id`, carrying through the provenance locator (page/field) where available
(Principle II). The Copilot service **validates** each returned citation against the
grounding set; a response citing anything not in the set is rejected and degraded.
Uncited conclusions are never surfaced. This is the primary defense against
hallucination and the operationalization of "no hidden reasoning."

### 7. Prompt versioning (Principle XII)

Every response records the `prompt_version` of the pinned template used. Prompt
templates are versioned, code-resident resources under version control; the active
version per intent is pinned at request time and stored on the message. No silent
change to Copilot behaviour is possible — a prompt change is a versioned, reviewable
change reflected in the attribution of every response produced under it.

### 8. Model version attribution (Principle XII)

Every response records the `model_version` returned by the `InferenceProvider` (the
contract already mandates non-empty `model_version` and `prompt_version`). Together
with the grounding snapshot's source versions (extraction/policy/model versions of the
underlying records), a response is **fully attributable**: an auditor can reconstruct
exactly what inputs, prompt, and model produced it.

**Reproducibility exemption (explicit).** Principle XII requires reproducibility of
**Evidence and Findings**. The Copilot produces **neither** — it produces explanations,
and LLM generation is not bit-reproducible in general. The Copilot is therefore
**exempt from bit-reproducibility** and instead guarantees **full attribution +
grounding-snapshot capture**: the same question re-asked against the same pinned inputs
may differ in wording, but never in what governed data and versions grounded it. A
Copilot response is an assistant output, never an attributable Finding, and MUST NOT be
treated as one. This exemption is recorded here so it is a deliberate architectural
position, not an accidental gap.

### 9. Least-data principle (Principle V)

The grounding set carries only the attributes necessary for the query's intent; surplus
personal data MUST NOT be placed in the prompt. Grounding is scoped to one application
and one tenant; cross-application data never enters an inference context. This aligns
with the `InferenceContext` contract's stated least-data requirement.

### 10. Prompt-injection defense

Evidence, OCR, and document text are **attacker-influenced** — they originate in
uploaded files. Copilot treats all retrieved content as **untrusted data, never as
instructions**. Content is inserted through structural templating that separates
instructions from data; the model is not permitted to let retrieved text alter its
task. Even a successful injection is contained: the Copilot has no write path and no
decision authority, so the worst case of a compromised prompt is a degraded or refused
answer, never a state change or an approval. Retrieved-content handling is a
first-class security requirement (Principle V), reviewed with the same rigour as
functional requirements.

### 11. Human authority (Principle I)

The Copilot augments, it does not decide. It surfaces evidence, explains, and
*suggests* — every lending decision remains the human reviewer's, unchanged by anything
Copilot does. Automation-bias risk is mitigated at the UX and language level (advisory
phrasing, assistant framing) and structurally (no decision events, no write path).
Trust precedes autonomy (Principle IV): Copilot expands assurance, not automation.

---

## Consequences

### What this enables
- A regulator-defensible AI assistant: every answer is grounded, cited, attributed,
  scoped, and audited.
- Structural (not merely behavioural) guarantees of read-only and non-authority.
- A clean first consumer of ADR-010 Query Ports.

### What this requires
- ADR-010 (Query Ports) as a prerequisite. **(Accepted.)**
- A generalized `InferenceContext` capable of carrying Finding/Policy/Review/Document
  grounding, not evidence only. **(Landed as `GroundingItem`; backwards compatible.)**
- A real, injection-resistant `InferenceProvider` for staging/production. **(Landed:
  `GeminiInferenceProvider` — Google Gemini AI Studio over REST, provider-agnostic via
  `Settings.inference_provider` + DI, with exponential-backoff retries. The mock
  inference provider has been removed; inference is real in every environment. See
  ARCHITECTURE.md §5.1.)**
- An immutable `copilot` schema (conversations, messages, citations, grounding
  snapshots) and synchronous audit event types. *(Sprint 7.)*
- A conversation-data retention policy (Principle V data-minimization). *(Governance
  decision, Sprint 7.)*

### What this prohibits
- Any Copilot write to Finding/Policy/Review/Evidence/Document.
- Any Copilot event that drives another context's state.
- Cross-application or cross-conversation memory.
- Uncited or ungrounded responses reaching the user.
- Treating a Copilot answer as a reproducible Finding.

---

## Alternatives Considered

**A. Copilot as an autonomous action-taker** (e.g. auto-request documents, auto-flag).
Rejected: violates Principle I and the read → enrich → return integration model.
Copilot proposes; humans act.

**B. Copilot with cross-application learned memory** for "smarter" answers. Rejected:
violates Principle V AI context isolation; introduces cross-tenant leakage risk;
incompatible with data minimization.

**C. Open-book generation** (model may use general knowledge). Rejected: unciteable,
unauditable, hallucination-prone; incompatible with Principles III/VIII/XII.

**D. Treat Copilot output as an attributable Finding** to satisfy Principle XII
literally. Rejected: dishonest — LLM output is not bit-reproducible; conflating
explanation with Finding corrupts the evidence chain. Attribution + grounding snapshot
is the correct, honest guarantee.

---

## References
- Engineering Constitution v1.1.0 — Principles I, III, IV, V, VIII, XII
- ADR-010 — Query Ports (read channel; prerequisite)
- ADR-007 — Transactional Outbox (audit remains synchronous)
- `src/mil/kernel/providers/inference.py` — `InferenceProvider` contract and the
  generalized `GroundingItem` / `InferenceContext`
- `src/mil/copilot/__init__.py`, `src/mil/copilot/ports.py` — bounded-context stub and
  the read-only Query Ports
