# Feature Specification: Underwriter Workspace

**Feature Branch**: `002-underwriter-workspace`

**Created**: 2026-07-05

**Status**: Draft

**Input**: User description: "Underwriter Workspace — the complete product specification for the primary daily working surface of the Mortgage Intelligence Layer (MIL): an AI-assisted, evidence-first workspace in which underwriters review applications ingested from a Loan Origination System, inspect AI-extracted evidence and grounded findings, interrogate a citation-backed Copilot, and record human verification/override decisions — at a scale of 100,000+ applications, meeting enterprise banking-software standards of speed, accessibility, and auditability comparable to Stripe Dashboard, Linear, GitHub, Notion, VS Code, and Bloomberg Terminal. Mandatory constraints: applications are never identified or searched by internal UUID, only by Borrower Name, Loan Number, or LOS Reference; the queue defaults to newest-first; the interface must remain responsive at tens of thousands of applications. This specification defines product architecture only — no frontend framework, component, or API implementation."

---

## Product Vision

The Underwriter Workspace is the surface where a human underwriter spends the majority of their working day. It is not a data-entry form bolted onto a database, and it is not a chat window bolted onto a language model. It is a **decision-support instrument**: a fast, evidence-anchored environment in which every AI-generated claim is traceable to a specific document, page, and field, and every human decision is captured with the same rigor a bank examiner would expect five years later.

MIL does not originate, approve, or reject loans. The Workspace's job is to make a qualified human faster and more confident — never to replace their judgment or obscure how a conclusion was reached (Constitution Principles I, III, IV). Every design decision in this specification is evaluated against one question: **does this make the evidence easier to trust, or does it just make the screen look busier?**

Three qualities are non-negotiable and take priority over visual polish when they conflict:

1. **Speed under load.** The Workspace must feel instantaneous at 100,000+ applications, thousands of evidence objects per application, and hundreds of documents per application. A beautiful interface that stutters at scale is a failed interface for this product.
2. **Evidence-first explainability.** No AI output is ever displayed without its supporting evidence being one interaction away. No AI output is ever displayed without stating what it found, why, on what evidence, with what confidence, and what the reviewer should do about it (Constitution Principle III).
3. **Auditable human authority.** Every verification, override, and escalation is a deliberate, attributed, reasoned act that the interface makes easy to perform correctly and hard to perform accidentally (Constitution Principles I, VIII).

The design reference class is professional instrument software — Bloomberg Terminal's density and keyboard-first speed, Linear's motion discipline and information hierarchy, Stripe Dashboard's trustworthy restraint, GitHub's evidence-linking patterns (diffs, blame, citations), VS Code's command palette and multi-pane workspace model, Notion's flexible-but-structured content blocks. It is explicitly **not** a generic admin template, a student-project CRUD dashboard, a generic ticketing CRM, or a general-purpose chat client with mortgage data pasted in.

---

## User Personas

### Primary Persona — Underwriter ("Priya")

Priya is a senior mortgage underwriter at a regional lender. She reviews 6–12 applications a day, each requiring 15–45 minutes of focused review, more if something is flagged. She is judged on both speed and accuracy, and she is legally and professionally accountable for every decision she signs off on. She does not want the AI to decide anything; she wants it to have already read every page of every document so she doesn't have to, and to show her exactly where it found what it found. Her primary tools today are the LOS itself (clunky, form-heavy) and manual document review (slow, error-prone at volume). She is not a technical user. She will not tolerate a slow interface, and she will not trust an answer she cannot verify in one click.

**Primary surfaces**: Application Queue, Application Workspace, Document Viewer, Evidence Explorer, Copilot, Verification/Override actions.

### Secondary Persona — Verification Officer ("Marcus")

Marcus works earlier in the pipeline, checking that AI-extracted evidence actually matches the source documents before an application reaches an underwriter. He is extremely high-volume and low-tolerance for friction — every extra click across hundreds of items per day compounds into real cost. He lives almost entirely in the Document Viewer and Evidence Explorer, rarely touches the Copilot, and never needs the Knowledge Graph.

**Primary surfaces**: Application Queue (filtered to his stage), Document Viewer, Evidence Explorer.

### Secondary Persona — Credit Analyst ("Dana")

Dana focuses on affordability and financial-consistency findings (income, debt, assets) rather than identity or property findings. She uses the same Application Workspace as Priya but with different default filters and a heavier reliance on the Knowledge Graph to trace conflicting figures across documents.

**Primary surfaces**: Application Workspace, Evidence Explorer, Knowledge Graph, Copilot.

### Tertiary Persona — Compliance / Audit Reviewer ("Tom")

Tom is read-only. He arrives after a decision has already been made, often weeks or months later, sometimes in response to a regulator or a customer complaint. He needs to reconstruct exactly what the AI found, what evidence supported it, what version of the model and policy produced it, who overrode what and why, and when — using only what is recorded in the product, with no reliance on tribal knowledge (Constitution Principle VIII). He does not use the Copilot to make findings, but he may use it, read-only, to ask "why" questions about a closed case.

**Primary surfaces**: Application Workspace (read-only mode), Audit Trail view.

### Tertiary Persona — Mortgage Operations Manager ("Elena")

Elena cares about team throughput, SLA aging, and bottlenecks across many underwriters' queues, not the content of any single case. Her needs are addressed by a **separate, future Operational Intelligence workspace** (see Future Expansion) built on the same backend module referenced in the platform's architecture. This specification's Dashboard is intentionally scoped to a single underwriter's personal queue, not org-wide operational analytics — conflating the two would dilute both. Elena is documented here so that scope boundary is explicit, not accidental.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Assess a Single Application (Priority: P1)

An underwriter opens an application assigned to them and works through it end to end: reviewing AI-generated findings with full explainability, inspecting the evidence and source documents behind each finding, and recording a verification or override decision with a mandatory reason. The application's state advances to reflect the decision.

**Why this priority**: This is the irreducible core of the product. Every other capability exists to get an underwriter into this loop faster or make it more trustworthy. If only this story existed — reachable via a direct link rather than a queue — the product would already deliver its central value proposition.

**Independent Test**: Deep-link directly to a seeded application with existing findings and evidence (bypassing the queue). Confirm the underwriter can read every finding's five explainability elements, open the supporting evidence and source document for each, and record a verification or override with a reason, resulting in a persisted, attributed decision.

**Acceptance Scenarios**:

1. **Given** an application assigned to the current user with AI-generated findings, **When** the underwriter opens it, **Then** every finding displays what was found, why, the supporting evidence, a confidence indicator, and a recommended action, with no finding ever shown missing any of these five elements.
2. **Given** a finding with supporting evidence, **When** the underwriter selects "view evidence," **Then** the exact source document opens with the relevant page and field visually highlighted, without a full page reload.
3. **Given** a finding the underwriter disagrees with, **When** they choose to override it, **Then** the system requires a non-empty reason before the override can be submitted, and the previous value, new value, reviewer identity, and timestamp are all recorded.
4. **Given** an override submission is in flight, **When** the network is briefly interrupted, **Then** the interface shows the action as pending (not silently succeeded), preserves the reviewer's typed reason without loss, and allows retry — the action is never shown as complete until the server confirms it.
5. **Given** all findings on an application have been verified or overridden, **When** the underwriter completes the review, **Then** the application's status updates to reflect the decision and the application leaves the underwriter's active queue.

---

### User Story 2 - Locate Applications Without Technical Identifiers (Priority: P1)

An underwriter, manager, or auditor finds a specific application using only information they would naturally have on hand — the borrower's name, the loan number, or the LOS reference — never an internal system identifier. Results appear in a queue that defaults to the newest applications first and remains fast regardless of total portfolio size.

**Why this priority**: This is a named, mandatory requirement, and it is also a practical precondition for nearly every other workflow. A search experience that leaks technical identifiers into the primary interface, or that degrades at scale, undermines trust in the entire product on first contact.

**Independent Test**: Against a seeded dataset of 100,000+ applications, search by a partial borrower name, then by exact loan number, then by LOS reference, and confirm correct, fast, ranked results each time, with the newest-first default queue visible with no search term entered.

**Acceptance Scenarios**:

1. **Given** a portfolio of 100,000+ applications, **When** the underwriter types a borrower's last name into search, **Then** matching applications appear ranked by relevance within one second, each result showing borrower name, loan number, LOS reference, and status — never an internal identifier as the primary label.
2. **Given** no search term entered, **When** the underwriter opens the queue, **Then** applications are sorted by most recently created or most recently updated (newest first) by default.
3. **Given** two applications share an identical borrower name, **When** both appear in search results, **Then** the loan number and LOS reference are shown alongside the name so the underwriter can disambiguate without opening either record.
4. **Given** a user pastes a raw system identifier into the search bar, **When** they submit it, **Then** the system treats it as free text like any other query — it is not a recognized, privileged search key, and no part of the primary interface exposes it as a valid or suggested way to find an application.

---

### User Story 3 - Interrogate Evidence via Grounded Copilot (Priority: P2)

Within a specific application, an underwriter asks a natural-language question ("What is the borrower's monthly income?", "Summarize the employment history", "Why was this finding flagged?") and receives an answer that is either fully grounded in that application's evidence — with citations the underwriter can open in one action — or an explicit statement that there is not yet enough evidence to answer, never a fabricated answer.

**Why this priority**: This is the product's clearest differentiator over a traditional LOS, but it is only trustworthy because of, and strictly subordinate to, the evidence model in Story 1. It is prioritized after the core review loop because a Copilot answer is only as valuable as the evidence-viewing experience it points into.

**Independent Test**: Against a seeded application with existing evidence, ask a question with a clear evidence-backed answer and confirm a cited, correct response; ask a question the evidence cannot support and confirm the safe "insufficient evidence" response is shown, visually distinct from a grounded answer.

**Acceptance Scenarios**:

1. **Given** an application with evidence supporting a direct question, **When** the underwriter asks that question, **Then** the answer is shown with one or more citations, each of which opens the exact source evidence or document location in one action.
2. **Given** an application without evidence supporting a question, **When** the underwriter asks it, **Then** the response explicitly states that insufficient evidence exists to answer, styled distinctly from a grounded answer, and never presents a claim without a citation.
3. **Given** a Copilot conversation about Application A, **When** the underwriter switches to Application B, **Then** no context, history, or evidence from Application A is visible or usable in Application B's Copilot session.
4. **Given** a Copilot response is being generated, **When** the underwriter is waiting, **Then** the interface shows a clear in-progress state (not a frozen screen) and the response streams in progressively rather than appearing only after full completion.

---

### User Story 4 - Investigate Discrepancies via Evidence Explorer & Relationships (Priority: P2)

An underwriter or credit analyst notices, or is alerted to, a potential inconsistency (e.g., income figures differing between a payslip and a bank statement) and needs to see every piece of evidence relevant to a given fact, across every document it came from, side by side, with the relationships between conflicting items made visually explicit.

**Why this priority**: Cross-document inconsistency is one of the highest-value findings the platform produces, and it is also the hardest to review carelessly — this workflow exists specifically to prevent a rushed reviewer from missing a conflict that a flat list of facts would bury.

**Independent Test**: Against a seeded application with two evidence items that materially conflict (e.g., two different declared incomes), confirm the conflict is visually surfaced without the reviewer needing to manually compare rows, and that each conflicting item traces to its own distinct source document and page.

**Acceptance Scenarios**:

1. **Given** two evidence items for the same underlying fact with different values, **When** the underwriter views the Evidence Explorer, **Then** the conflict is visually flagged (not merely listed neutrally alongside non-conflicting evidence).
2. **Given** an evidence item, **When** the underwriter requests its relationships, **Then** they can see which findings it supports, which documents it came from, and which other evidence items relate to the same fact, without leaving the current application context.
3. **Given** an evidence item with no known conflicts, **When** viewed, **Then** it is not visually flagged as a conflict — the system does not manufacture uncertainty where none exists.

---

### User Story 5 - Operational Triage of the Full Queue at Scale (Priority: P2)

An underwriter or manager applies filters (status, SLA age, document type, assigned reviewer, flagged findings, etc.) and sort orders across a queue of 100,000+ applications, saves a personal view they use daily, and navigates the results by keyboard, with the interface remaining responsive throughout.

**Why this priority**: This is the difference between a workspace that survives contact with a real, large portfolio and one that only works in a demo. It is prioritized after the single-application and search stories because it is an efficiency multiplier on top of them, not a replacement for them.

**Independent Test**: Against a seeded dataset of 100,000+ applications, apply a multi-condition filter, confirm results and total counts return quickly, save the filter as a named view, reload the workspace, and confirm the saved view is available and reproduces the same results.

**Acceptance Scenarios**:

1. **Given** a queue of 100,000+ applications, **When** the underwriter applies a filter combination, **Then** filtered results and an accurate total count are shown without the interface freezing or the browser tab becoming unresponsive.
2. **Given** a filter combination the underwriter uses often, **When** they save it as a named view, **Then** it is available on their next visit without needing to be reconstructed.
3. **Given** the underwriter is scrolling a large result set, **When** they scroll far down and then back up, **Then** their position and applied filters are preserved, and returning from an opened application returns them to the same scroll position and filter state.

---

### User Story 6 - Stay Informed via Notifications (Priority: P3)

An underwriter receives timely, relevant notifications (new assignment, SLA risk, a colleague's override on a case they are watching, a document that failed processing) without needing to manually poll their queue, and can act on a notification directly rather than only being informed by it.

**Why this priority**: This is a meaningful efficiency and risk-reduction improvement, but the workspace is fully functional and valuable without it — an underwriter can still find and review applications by checking the queue directly.

**Independent Test**: Trigger a seeded event (new assignment) for a logged-in underwriter and confirm a notification appears within the defined latency window, is actionable (navigates to the relevant application), and can be marked read/dismissed.

**Acceptance Scenarios**:

1. **Given** an application is newly assigned to the underwriter, **When** the assignment occurs, **Then** a notification appears in the workspace within 30 seconds without a manual page refresh.
2. **Given** an unread notification referencing an application, **When** the underwriter selects it, **Then** they are taken directly to the relevant application and, where applicable, the relevant finding or evidence within it.
3. **Given** multiple notifications of the same type accumulate, **When** the underwriter views the notification list, **Then** related notifications are grouped or summarized rather than presented as an undifferentiated flood.

---

### Edge Cases

- **Application still processing**: A newly ingested application has no findings and incomplete evidence yet. The Workspace must show an explicit in-progress state per document (per Constitution Principle XII, extraction is versioned and attributable), never an empty screen indistinguishable from "nothing here" or a broken page.
- **Document failed ingestion**: A document that failed OCR or extraction must surface its failure state and reason clearly at both the document list and document viewer level — never silently disappear or appear identical to a successfully processed document.
- **Zero evidence, zero findings**: An application with no extractable evidence yet (e.g., only unsupported file types uploaded) must present a clear, actionable empty state, not an error.
- **Copilot insufficient grounding**: Must always be visually and textually distinct from both a normal answer and an error — it is a correct, expected outcome, not a failure state.
- **Duplicate or near-duplicate borrower names**: Must never create ambiguity in search results, queue rows, or Copilot citations — loan number and LOS reference always accompany the name.
- **Extremely long field values** (long legal names, long property addresses, long free-text findings rationale): must truncate gracefully with full value available on demand, never break layout or silently clip meaning-bearing text without indication.
- **Session expiry mid-task**: An underwriter mid-way through typing an override reason on a long document review must not lose that unsaved input on re-authentication.
- **Concurrent access to the same application**: Rather than a hard lock (which creates support burden, deadlock risk, and blocks legitimate handoffs), the Workspace shows a lightweight, non-blocking indicator when the underlying record has changed since it was loaded, with a one-action refresh — see Enterprise UX Guidelines for the rationale against pessimistic locking here.
- **Very large document** (a 150+ page loan file): the Document Viewer must never require the entire document to be loaded before the first page is usable.
- **Filter combination yields zero results**: presented as a specific, actionable empty state ("no applications match these filters" with a clear way to adjust them), never as an error or a blank table.
- **User attempts to search using a pasted internal identifier**: treated as ordinary free text with no special handling — see User Story 2, Acceptance Scenario 4. There is no hidden or advanced mode that promotes UUID-based lookup to a first-class search pattern anywhere in this workspace.
- **Reduced-motion or high-contrast OS preference is enabled**: all motion and contrast-dependent affordances degrade gracefully to fully functional, non-animated, high-contrast equivalents — never a broken or illegible state.
- **Offline or degraded network mid-session**: the workspace clearly indicates connectivity loss, prevents actions that cannot be safely queued (see Assumptions), and recovers gracefully once connectivity returns, without data loss for anything already in progress.

---

## Requirements *(mandatory)*

### Functional Requirements

#### A. Information Architecture & Navigation

- **FR-001**: The workspace MUST organize all functionality under a small, fixed set of top-level destinations (at minimum: Dashboard, Application Queue, and, contextually, an open Application Workspace); it MUST NOT rely on deep, multi-level hierarchical navigation menus to reach primary functions.
- **FR-002**: The workspace MUST provide a persistent, global command palette reachable by a single keyboard shortcut from anywhere in the product, offering navigation to any destination, any recently viewed application, and any primary action, ranked by relevance and recency.
- **FR-003**: The workspace MUST make the currently open application's identity (borrower name, loan number, LOS reference, status) persistently visible while working within it, regardless of which sub-view (documents, evidence, Copilot, etc.) is active.
- **FR-004**: Navigating into an application MUST NOT require leaving or losing the state (filters, scroll position, sort order) of the queue the underwriter came from; returning MUST restore that state.
- **FR-005**: The workspace MUST support deep-linking: any application, document, evidence item, or finding MUST be reachable via a direct, shareable link that a colleague or auditor can open to land on that exact context.
- **FR-006**: Internal system identifiers (database keys, UUIDs) MUST NOT appear as the primary label, sort key, or user-facing search key anywhere in the primary navigation, queue, search, or workspace surfaces.
- **FR-007**: The workspace MUST clearly and persistently indicate the identity and role of the currently authenticated user, and MUST make signing out a single, always-reachable action.
- **FR-008**: Every primary destination MUST be reachable within two interactions (e.g., one click/keystroke to a top-level destination, one further click/keystroke to a specific record) from anywhere else in the product.

#### B. Search

- **FR-009**: Global search MUST accept borrower name (full or partial), loan number, and LOS reference as first-class query inputs, and MUST return relevant results from any of these fields without the user specifying which field they are searching.
- **FR-010**: Search MUST NOT accept, suggest, or document internal system identifiers as a supported query type; a pasted identifier MUST be treated as plain text with no special-cased matching behavior.
- **FR-011**: Search results MUST display, for every result, at minimum: borrower name, loan number, LOS reference, current status, and last-updated time — sufficient to disambiguate any result without opening it.
- **FR-012**: Search MUST return results within the performance targets defined in Success Criteria regardless of total portfolio size.
- **FR-013**: Search MUST be reachable from anywhere in the workspace via a single, consistent, keyboard-accessible entry point (not only from the queue screen).
- **FR-014**: An empty search (no query entered) MUST show the default newest-first queue rather than an empty or blank state.
- **FR-015**: Search MUST tolerate common real-world input variation (case-insensitivity, partial name matches, common formatting variants of loan/reference numbers) without requiring exact-match input from the user.

#### C. Application Queue

- **FR-016**: The Application Queue MUST default to sorting by newest first (most recently created or most recently updated, consistently defined) with no user action required to achieve this ordering.
- **FR-017**: The queue MUST remain fully interactive (scrolling, sorting, filtering) at a portfolio size of 100,000+ applications without visibly degraded responsiveness, per Success Criteria.
- **FR-018**: Each queue row MUST surface, at minimum: borrower name, loan number, LOS reference, current status, assigned reviewer (if any), an SLA/age indicator, and a summary indicator of flagged or unresolved findings — without requiring the row to be opened.
- **FR-019**: The queue MUST support sorting by any of its displayed columns, and filtering by status, assigned reviewer, document/evidence completeness, SLA risk, and presence of flagged findings, in combination.
- **FR-020**: The queue MUST support saving a named combination of filters and sort order as a personal, reusable view, and switching between saved views without re-specifying criteria.
- **FR-021**: The queue MUST visually distinguish applications that are SLA-at-risk or overdue from those that are on track, using a signal that does not rely on color alone (see Accessibility).
- **FR-022**: Selecting an application from the queue MUST open the Application Workspace without a full page reload, and MUST preserve the underwriter's place in the queue for their return.
- **FR-023**: The queue MUST support keyboard-only row navigation and selection (see Keyboard Navigation).
- **FR-024**: The total count of applications matching the current filter MUST always be visible, even when only a page or window of rows is rendered.
- **FR-025**: Bulk, multi-application actions (e.g., bulk reassignment) MAY be supported, but MUST NEVER include bulk verification or bulk override of AI findings — every override remains an individually reasoned, individually attributed act (Constitution Principle I).

#### D. Dashboard ("My Work")

- **FR-026**: The Dashboard MUST summarize, for the current underwriter, at minimum: applications currently assigned to them, applications approaching or past SLA, and applications with recent activity relevant to them (e.g., a colleague's override on a case they are watching).
- **FR-027**: The Dashboard MUST provide a one-action path from any summarized item directly into the relevant application.
- **FR-028**: The Dashboard MUST be scoped to the current underwriter's own work; it MUST NOT present organization-wide or cross-team operational metrics (that capability belongs to a separate, future operational-management surface — see Future Expansion).

#### E. Application Workspace (record-level shell)

- **FR-029**: The Application Workspace MUST present, at minimum, the following as clearly navigable regions within one application context: an overview/summary, findings, evidence, documents, and Copilot — without requiring a full page reload to move between them.
- **FR-030**: The Application Workspace MUST make the application's current lifecycle status, and the set of actions available at that status, unambiguous at all times.
- **FR-031**: The Application Workspace MUST show, for every AI-generated finding, all five explainability elements (what, why, supporting evidence, confidence, recommended action) with no exceptions (Constitution Principle III); a finding that cannot populate all five MUST NOT be displayed to the reviewer.
- **FR-032**: Every finding MUST provide a one-action path to its supporting evidence, and every evidence item MUST provide a one-action path to its exact source document location.
- **FR-033**: Recording a verification of a finding MUST require no more than one explicit confirming action; recording an override MUST require a non-empty, explicit reason before submission is possible.
- **FR-034**: Verification and override actions MUST NOT be reflected as complete in the interface until the server has confirmed the write; on failure, the reviewer's input (including any typed reason) MUST be preserved for retry, never silently discarded.
- **FR-035**: The Application Workspace MUST make the full history of prior verifications, overrides, and status transitions for the application available for review, attributed to the actor and timestamped (Constitution Principle VIII).
- **FR-036**: When the underlying application record has changed on the server since it was loaded into the Workspace (e.g., a colleague acted on it), the interface MUST surface a clear, non-blocking indicator and a one-action way to refresh — it MUST NOT silently allow the reviewer to act on stale data without warning, and MUST NOT impose a hard lock that prevents any other user from opening the same record.
- **FR-037**: A read-only mode of the Application Workspace MUST be available to auditor/compliance roles, presenting identical evidentiary and decision content with all action controls (verify, override, escalate) absent rather than merely disabled-but-visible.

#### F. Document Viewer

- **FR-038**: The Document Viewer MUST render the first page of a document and make it usable before the remainder of a large document has finished loading.
- **FR-039**: The Document Viewer MUST support jumping directly to a specific page and, where field-location provenance exists, to a specific field on that page, from a link originating in a finding, evidence item, or Copilot citation.
- **FR-040**: The Document Viewer MUST visually highlight the specific region of a page corresponding to a piece of evidence, distinguishable from the surrounding page content.
- **FR-041**: The Document Viewer MUST clearly indicate a document's processing state (pending, in progress, completed, failed) and, for a failed state, the reason, without requiring the reviewer to leave the viewer to discover it.
- **FR-042**: The Document Viewer MUST support standard read navigation (next/previous page, page number entry, zoom) via both pointer and keyboard.
- **FR-043**: The Document Viewer MUST NOT require downloading the source file to view it; viewing MUST be possible directly within the workspace.
- **FR-044**: Where multiple documents exist for an application, the Document Viewer MUST allow switching between them without losing the reviewer's place in the application's other regions (findings, evidence).

#### G. Evidence Explorer

- **FR-045**: The Evidence Explorer MUST list every evidence item extracted for the application, each showing its value, source document, page, extraction confidence, and verification status.
- **FR-046**: The Evidence Explorer MUST support filtering and grouping evidence by type (e.g., income, identity, property, employment) and by source document.
- **FR-047**: The Evidence Explorer MUST visually flag evidence items that conflict with another evidence item representing the same underlying fact, and MUST make both conflicting items simultaneously viewable for comparison.
- **FR-048**: Every evidence item MUST provide a one-action path to the finding(s) it supports and to its exact source location in the Document Viewer.
- **FR-049**: The Evidence Explorer MUST display extraction confidence using a consistent, immediately scannable visual treatment across the entire workspace (not a different scale or style per screen).
- **FR-050**: The Evidence Explorer MUST remain responsive when an application has thousands of evidence items, per Success Criteria.

#### H. Findings, Verification & Override

- **FR-051**: Findings MUST be presented grouped or prioritized so that flagged/high-risk findings are not visually subordinate to routine, unremarkable ones — a reviewer scanning quickly must not be able to miss a flagged finding by design.
- **FR-052**: Every override MUST capture and permanently retain: the reviewer's identity, the previous value, the new value, the reason, and the timestamp (Constitution Principle VIII); none of these MAY be edited or deleted after submission.
- **FR-053**: The interface MUST distinguish, at a glance, between a finding that is unreviewed, verified, overridden, and escalated.
- **FR-054**: Escalating a finding to another role MUST be possible directly from the finding, and MUST require the escalating reviewer to state why.
- **FR-055**: The interface MUST make it structurally difficult to override a finding without having viewed its supporting evidence at least once in the current session (e.g., the evidence view is the natural, one-action path to the override control, not a separate, avoidable step) — the goal is to make the safe path the fast path, not to add a blocking gate.

#### I. Copilot Interface

- **FR-056**: The Copilot MUST always be scoped to a single application; it MUST NOT retain or expose context, history, or evidence from any other application (Constitution Principle V — AI context isolation).
- **FR-057**: Every Copilot response MUST either include one or more citations resolvable to specific evidence or documents within the current application, or explicitly state that available evidence is insufficient to answer — a response containing neither is not a permitted state.
- **FR-058**: Citations in a Copilot response MUST be individually selectable, each opening its specific source (evidence item or document location) in one action.
- **FR-059**: The Copilot MUST visually distinguish a grounded answer from an "insufficient evidence" response using more than color alone (see Accessibility).
- **FR-060**: The Copilot MUST show a distinct, immediate in-progress state while a response is being produced, and MUST progressively reveal the response as it becomes available rather than only upon full completion.
- **FR-061**: The Copilot MUST record the model version and prompt version associated with every response as part of the application's auditable history (Constitution Principle XII), without requiring the reviewer to take any extra action for this to occur.
- **FR-062**: The Copilot interface MUST remain anchored to, and contextually presented alongside, the application it is grounded in — it MUST NOT be offered as a standalone, full-screen, general-purpose chat destination.
- **FR-063**: The underwriter MUST be able to review the full history of prior Copilot questions and answers for an application, including their citations, at any later time.

#### J. Knowledge Graph / Relationship View

- **FR-064**: The workspace MUST provide a relationship view for a given evidence item or finding, showing what it supports, what it conflicts with, and what document(s) it derives from, scoped to the current application.
- **FR-065**: The relationship view MUST remain legible and usable when an application has hundreds of evidence items and findings — it MUST NOT become an unreadable, undifferentiated tangle at realistic data volumes; where a full graph would be illegible, the interface MUST offer a focused, filtered, or list-based alternative view of the same relationships.
- **FR-066**: Every node in the relationship view MUST provide a one-action path to its full detail (the finding, evidence item, or document it represents).
- **FR-067**: The relationship view MUST be an optional, on-demand investigative tool, not a required step in the primary review workflow — most routine reviews must be completable without ever opening it.

#### K. Filtering & Saved Views

- **FR-068**: Filters MUST be combinable (AND semantics across filter categories, at minimum) and MUST show, before being applied, an estimate or exact count of matching results where feasible.
- **FR-069**: Every applied filter MUST be individually visible and individually removable, without needing to clear and reconstruct the entire filter set.
- **FR-070**: Saved views MUST be personal by default and MUST support being explicitly shared with a team, without requiring every team member to reconstruct the same criteria independently.
- **FR-071**: Clearing all filters MUST be a single, always-available action.

#### L. Tables (Data Grids)

- **FR-072**: Any table presenting a list of records (applications, documents, evidence, notifications, audit entries) MUST support column sorting where the underlying data supports it, and MUST NOT require loading the entire dataset to sort or scroll it.
- **FR-073**: Tables MUST support keyboard-only row navigation, selection, and activation (see Keyboard Navigation).
- **FR-074**: Tables presenting monetary, date, or percentage values MUST format them consistently across the entire workspace.
- **FR-075**: A table with zero matching rows MUST present a specific, contextual empty state rather than a bare blank area.

#### M. Forms & Data Entry

- **FR-076**: Every form field capturing a reason, justification, or free-text decision input MUST validate for non-empty content before allowing submission, and MUST clearly indicate why submission is blocked when it is.
- **FR-077**: Forms MUST preserve in-progress input across an interruption (navigation away and back within the same session, brief network loss, session re-authentication) rather than discarding it.
- **FR-078**: Destructive or hard-to-reverse actions (e.g., an override that materially changes a finding's disposition) MUST require an explicit confirming step distinct from the field entry itself.
- **FR-079**: Form validation errors MUST be associated with their specific field, not only summarized generically at the top or bottom of the form.

#### N. Empty, Loading & Error States

- **FR-080**: Every primary view MUST define and display a distinct empty state (no data yet, e.g., a new application with no documents) that explains the situation and, where applicable, the next expected action or timeframe — never a bare blank screen.
- **FR-081**: Every primary view MUST define and display a distinct loading state that appears within 100ms of a data-fetching action being initiated, so the interface never appears frozen or unresponsive.
- **FR-082**: Every primary view MUST define and display a distinct error state that explains what failed in plain language, offers a retry action where retrying is meaningful, and never exposes raw technical error detail (stack traces, internal codes) as the primary message to the user.
- **FR-083**: A partial failure (e.g., one document failed to process while others succeeded) MUST be represented at the granularity of the failure — it MUST NOT cause the entire application view to appear as failed or unavailable.

#### O. Notifications

- **FR-084**: The workspace MUST notify the current user, within 30 seconds of the triggering event, of at minimum: new assignment, an application they are watching approaching or breaching SLA, and a status change on an application they are watching.
- **FR-085**: Notifications MUST be individually actionable (navigate directly to the relevant context) and individually or collectively markable as read.
- **FR-086**: Repeated notifications of the same type and subject MUST be grouped or summarized rather than presented as separate, undifferentiated entries.
- **FR-087**: The notification affordance MUST indicate unread count or presence persistently and unobtrusively from anywhere in the workspace.

#### P. Keyboard Navigation & Command Palette

- **FR-088**: Every primary workflow described in User Scenarios & Testing MUST be fully completable using only the keyboard, with no loss of available functionality compared to pointer use.
- **FR-089**: A single, consistent keyboard shortcut MUST open the global command palette from anywhere in the workspace.
- **FR-090**: Focus order MUST follow a logical, predictable sequence matching the visual layout on every screen, and the currently focused element MUST always be visibly indicated.
- **FR-091**: Keyboard shortcuts, where offered for frequent actions, MUST be discoverable in-product (e.g., via the command palette or a help overlay), not documented only externally.
- **FR-092**: No keyboard shortcut MAY conflict with a standard browser or assistive-technology shortcut in a way that removes the user's ability to use that underlying shortcut.

#### Q. Accessibility

- **FR-093**: The workspace MUST conform to WCAG 2.1 Level AA across all primary screens and workflows.
- **FR-094**: No information (status, SLA risk, evidence conflict, verification state) MAY be conveyed by color alone; a second, non-color signal (icon, text label, pattern) MUST always accompany it.
- **FR-095**: All interactive elements MUST have an accessible name usable by screen readers, and all meaningful images, icons, and visual indicators conveying information MUST have an equivalent text alternative.
- **FR-096**: The workspace MUST support operating-system-level high-contrast and reduced-motion preferences, degrading to fully functional, non-animated, high-contrast equivalents without loss of information or capability.
- **FR-097**: Text and interactive-element contrast MUST meet WCAG AA minimums in both a light and a dark presentation of the interface.
- **FR-098**: Dynamic content updates that are important for the user to notice (e.g., a new finding appearing, a Copilot answer completing) MUST be announced to assistive technology, not only presented visually.

#### R. Responsive Behaviour

- **FR-099**: The workspace's primary review workflows MUST remain fully usable on a standard laptop display; below that width, the product MAY present a deliberately reduced, read-oriented experience rather than attempting full data-entry parity (see Assumptions).
- **FR-100**: Any region that adapts its layout by width (e.g., panels collapsing, tables reflowing) MUST never lose access to information or actions available at wider widths — it MUST relocate them, not remove them.
- **FR-101**: Print or export of a document or evidence view, where offered, MUST preserve the evidentiary context (source, page, provenance) rather than presenting only the raw value.

### Key Entities *(include if feature involves data)*

- **Application (view model)**: The underwriter-facing representation of a mortgage application: borrower name(s), loan number, LOS reference, lifecycle status, assigned reviewer, SLA/age, document count, evidence count, count of unresolved/flagged findings, last activity timestamp. Never presents an internal identifier as its primary label.
- **Document (view model)**: A source file associated with an application: type, original filename, page count, ingestion/processing status (and failure reason if applicable), and the count of evidence items derived from it.
- **Evidence Item**: A single provenance-bearing fact: its value, the document and page it came from, its field location where available, its extraction confidence, its extraction method/version, and its current verification status. Carries all seven provenance attributes required by Constitution Principle II.
- **Finding**: An AI-generated observation derived from one or more evidence items: what was found, why, supporting evidence references, a confidence label, a recommended action, and a lifecycle state (unreviewed, verified, overridden, escalated).
- **Verification / Override Record**: An immutable record of a human decision on a finding: reviewer identity, previous value, new value, reason, and timestamp. Never edited or deleted after creation.
- **Copilot Session, Message, and Citation**: A conversation scoped to exactly one application; each message pair (question, answer) carries zero or more citations, each resolvable to a specific evidence item or document location, plus the model and prompt version attributable to that answer.
- **Saved View / Filter**: A named, reusable combination of filter criteria and sort order over the Application Queue, owned by a user and optionally shared with a team.
- **Notification**: A typed, timestamped, attributable alert referencing a specific application (and, where applicable, a specific finding or evidence item), with a read/unread state.
- **Audit Trail Entry**: A read-only, chronological reconstruction of every significant action taken on an application — ingestion, extraction, findings generated, verifications, overrides, escalations, status transitions, and Copilot interactions — sufficient to reconstruct the complete lifecycle of the application without any external source (Constitution Principle VIII).
- **Relationship (Knowledge Graph edge)**: A typed connection between two entities relevant to a single application — for example, evidence *supports* finding, document *contains* evidence, finding *conflicts with* finding.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An underwriter can locate any application by borrower name, loan number, or LOS reference — never an internal identifier — in under 2 seconds, across a portfolio of 100,000+ applications.
- **SC-002**: Queue and table interactions (scrolling, sorting, filtering) register within 100 milliseconds and reflect updated data within 1 second, regardless of total application count.
- **SC-003**: From selecting an application in the queue, its first finding and supporting evidence are visible to the underwriter within 2 seconds.
- **SC-004**: 100% of AI-generated findings shown to a reviewer display all five explainability elements (what, why, evidence, confidence, recommended action); zero findings are ever displayed missing any element.
- **SC-005**: 100% of Copilot responses either present at least one openable citation or explicitly state insufficient evidence; zero responses present an uncited claim as fact.
- **SC-006**: A new underwriter can complete their first full application review — evidence check through recorded decision — in under 15 minutes relying only on in-product guidance, with no external training session required.
- **SC-007**: 100% of verification, override, and escalation actions are fully reconstructable after the fact from the audit trail alone, with zero reliance on information outside the product.
- **SC-008**: Every primary workflow in User Scenarios & Testing is completable using only a keyboard, with no reduction in available functionality versus pointer use.
- **SC-009**: All primary screens and workflows meet WCAG 2.1 Level AA, confirmed by both automated and manual audit.
- **SC-010**: 95% of queue filter, search, and sort operations return results in under 1 second at a portfolio scale of 100,000+ applications.
- **SC-011**: An underwriter never needs to manually refresh the page to see a new assignment, SLA change, or status update relevant to them — such updates surface within 30 seconds of occurring.
- **SC-012**: In post-adoption feedback, at least 90% of underwriters rate the workspace as faster and less effortful for daily review than their prior tooling.

---

## Assumptions

- **Single-tenant working context.** Each authenticated session operates within one lending institution's data; cross-institution tenant switching within a single session is out of scope for this specification (consistent with the platform's phased multi-tenancy roadmap) and is addressed only as Future Expansion.
- **Role scope for this specification.** This specification defines the workspace primarily for the Underwriter persona, with the Verification Officer and Credit Analyst personas served by the same surfaces under role-appropriate defaults and permissions. A dedicated, distinct workspace for the Operations Manager persona (team-wide throughput and SLA analytics) is explicitly out of scope here and is addressed under Future Expansion, to keep this specification's Dashboard sharply scoped to individual work rather than diluted into a partial analytics product.
- **Copilot is always application-scoped.** There is no cross-application or portfolio-wide Copilot mode in this specification; this follows directly from the platform's AI context isolation requirement (Constitution Principle V) and is treated as a firm design constraint, not an open question.
- **Network connectivity is assumed, with graceful degradation, not offline-first operation.** The workspace requires network connectivity for its data and AI-backed capabilities; brief interruptions are handled gracefully (see Error Handling requirements), but full offline operation is out of scope for this specification.
- **Desktop-first, laptop-minimum.** The primary design target is a standard laptop or desktop display used for extended daily work; a native mobile application is out of scope, and a reduced, read-oriented experience below laptop width is an acceptable degradation (see Responsive Behaviour), not a defect.
- **Optimistic UI is a targeted technique, not a blanket policy.** It is deliberately withheld from audit-critical writes (verification, override, escalation, status transition) where the cost of showing an unconfirmed state as final is unacceptable, and is appropriate for low-risk, easily reversible preference actions (e.g., saved view creation, column sort, filter selection) where responsiveness matters more than write confirmation. This distinction is treated as a firm design rule, not a case-by-case implementation choice (see Enterprise UX Guidelines).
- **"Newest first" is defined consistently as most-recent-activity-first** (creation or last update, whichever is more recent) unless a specific saved view overrides it — this is treated as the platform-wide default ordering semantic.
- **Existing backend capabilities are treated as authoritative and stable.** This specification assumes the previously validated backend (evidence provenance, findings, grounded Copilot, audit events, real-time-capable job/notification infrastructure) as its foundation and does not propose backend redesign; where a requirement here implies backend capability not yet confirmed to exist (e.g., sub-second search across 100,000+ records, near-real-time notification delivery), it is flagged as a dependency for the implementation-planning phase rather than resolved here.

---

## Design Rationale — Challenging Weaker Alternatives

This section documents explicit trade-off decisions made against plausible, weaker alternatives, per the requirement to challenge assumptions rather than default to them silently.

- **Virtualized, paginated tables over naive infinite scroll.** Infinite scroll alone loses scan-ability, back-button integrity, and a stable sense of "how much is left" — all of which matter when triaging tens of thousands of records under time pressure. The stronger enterprise pattern (as used by Linear, GitHub, and Bloomberg-class tools) is a virtualized, windowed table with explicit, cheap pagination/jump controls and a persistently visible total count — infinite scroll's convenience is not worth its loss of orientation at this scale.
- **Soft conflict detection over pessimistic locking for concurrent application access.** Hard record locking in a multi-reviewer environment creates deadlocks, support tickets ("why can't I open this application"), and blocks legitimate handoffs (e.g., a supervisor stepping in). A visible "this has changed, refresh to see the latest" indicator, matching patterns used by Notion and Linear, achieves the real goal — preventing a decision on stale data — without the operational cost of locking.
- **Selective, not universal, optimistic UI.** Applying optimistic UI everywhere is a common but weak default for a system whose core value proposition is auditability. Showing an override as "done" before the server has actually committed the audit record is a direct contradiction of Constitution Principle VIII; optimistic UI is reserved for actions where being wrong costs nothing (UI preferences), never for actions that constitute the regulatory record.
- **A firm, product-wide ban on UUID-based search, not a soft de-emphasis.** A weaker interpretation of the mentor requirement might quietly still support ID-based lookup as a hidden or advanced fallback "for power users." This specification takes the stronger position: it is not supported anywhere in this product, at any privilege level, because any exposure — even hidden — becomes a support-team habit that reintroduces exactly the confusion the requirement exists to prevent. If a genuine technical support need exists, it belongs in a separate internal tool, not this workspace.
- **An application-anchored Copilot panel over a general-purpose chat destination.** A full-screen, ChatGPT-style Copilot invites users to treat it as a general assistant, encourages ambiguous scope ("which application are we even talking about?"), and is the single biggest risk to the AI-context-isolation guarantee (Constitution Principle V). Anchoring the Copilot visually and functionally to one open application at a time is a deliberately stronger constraint than a more "modern-feeling" floating assistant would suggest.
- **A flat, command-palette-first navigation model over deep hierarchical menus.** Generic admin templates and CRMs favor multi-level sidebar trees. At the density and daily-use frequency this product targets, a Bloomberg/VS Code-style flat structure with a keyboard-driven command palette measurably reduces the number of interactions between "I know what I want" and "I'm looking at it," which matters far more here than a menu that looks organized on first impression.

---

## Design System Foundations

### Typography

- A single, highly legible typeface family MUST be used for interface text, distinct from any typeface used for rendering document content (which must preserve the source document's own appearance).
- A constrained type scale (a small, fixed set of sizes — no more than 6–7 steps from smallest label to largest heading) MUST be used consistently; ad hoc font sizes are not permitted.
- Numeric and financial data (currency, percentages, dates, loan numbers) MUST use a tabular/monospaced-figure treatment so columns of numbers align visually — a detail that separates instrument-grade interfaces (Bloomberg, Stripe) from generic dashboards.
- Line length for dense reading content (findings rationale, Copilot answers) MUST be constrained to a comfortable reading measure, not allowed to stretch full-width on large displays.

### Colour System

- A restrained, deliberate palette MUST be used: a neutral base (for structure, text, backgrounds), a single accent color (for primary actions and focus), and a small, fixed set of semantic colors (success/verified, warning/at-risk, danger/conflict-or-error, informational) — never an ad hoc or expanding color set per screen.
- Semantic color MUST always be paired with a non-color signal (icon or label) per Accessibility requirements — color is a reinforcing signal, never the only signal.
- The workspace MUST support both a light and a dark presentation, both meeting WCAG AA contrast, given the extended daily usage pattern (comparable to VS Code and Linear's dual-theme support for all-day professional use).
- Color MUST NOT be used decoratively; every color used in the interface must be traceable to a specific structural or semantic meaning.

### Spacing System

- A single, consistent spacing scale (a fixed step sequence, e.g., a small base unit and its multiples) MUST govern all padding, margin, and gap values across the product — no arbitrary one-off spacing values.
- Information density MUST default toward the denser end of enterprise norms (this is a professional instrument used 8 hours a day by expert users, not a consumer app optimized for first-time comprehension) while preserving WCAG-compliant touch/click target sizes and clear visual grouping.

### Component Library Principles

- Every recurring pattern (status indicator, confidence indicator, citation chip, evidence highlight, empty state, loading state, error state, notification) MUST be defined once as a single, consistent pattern and reused everywhere it applies — the same concept MUST never be represented two different visual ways in different parts of the product.
- Components MUST be specified with every state they can be in (default, hover, focus, active, disabled, loading, error) as part of the design system, not left to be improvised per screen during implementation.
- Every interactive component MUST have a defined, visible focus state meeting accessibility contrast requirements.

### Motion Guidelines

- Motion MUST be purposeful (indicating a state change, a spatial relationship, or a loading process) — never decorative.
- Motion durations MUST be short (consistent with a professional tool used all day — motion that is pleasant once becomes friction at hundreds of repetitions per day).
- All motion MUST fully respect an operating-system-level reduced-motion preference, degrading to an instant or minimal-motion equivalent that preserves all information conveyed by the animation.

---

## Performance Strategy

- The workspace MUST treat "loading the entire dataset" as an anti-pattern at every scale addressed by this specification (100,000+ applications, thousands of evidence items, hundreds of documents per application); every list-type view MUST be designed around windowed rendering and incremental/paginated data retrieval rather than full-set loading.
- Every primary view MUST distinguish between data needed to render the first meaningful content and data that can be retrieved progressively afterward (e.g., an application's identity and first finding versus its full evidence history) — first meaningful content must never wait on the slowest, least-important data.
- Long-running AI-backed operations (Copilot responses, in some cases extraction status) MUST be presented as they progressively become available (streaming/incremental reveal) rather than as a single blocking wait for full completion.
- Background data (e.g., queue rows updating as underlying applications change) MUST be refreshed without disrupting the user's current scroll position, selection, or in-progress input.
- Performance targets defined in Success Criteria are non-negotiable constraints on scope: a feature that cannot meet them at the stated scale must be redesigned before launch, not shipped with a caveat.

---

## State Management & Data Strategy

- The server is always the source of truth. Any locally held representation of application, evidence, finding, or audit data is a cache of server state, never an independent record, and MUST be reconcilable back to the server at any time.
- Data freshness MUST be tiered by consequence: data that informs an audit-critical decision (findings, evidence, verification status) MUST be confirmed fresh (or explicitly marked as possibly stale, per FR-036) before a reviewer acts on it; data that is purely informational (e.g., a queue row's SLA-age indicator) MAY tolerate brief staleness with background refresh.
- Writes are categorized by consequence (see Assumptions — optimistic UI policy): audit-critical writes are confirmed-then-reflected; low-risk preference writes may be reflected-then-confirmed.
- Every piece of state the user has invested effort in (typed reason, applied filters, scroll position, open panel) MUST survive incidental interruptions (navigation, brief disconnection, tab backgrounding) within the same session.

---

## API Integration Strategy

*(Product-level contract expectations toward the existing, stable backend — not an implementation or wire-format specification.)*

- All application, evidence, finding, and document data presented in this workspace MUST originate from the existing platform's evidence and finding services; this specification introduces no new source of truth and no shadow data store.
- List-type queries (queue, evidence lists, notification lists, audit trails) MUST be retrievable in a paginated, cursor-or-offset-consistent manner suitable for windowed rendering at the stated scale — a query model that requires retrieving an entire result set to display any of it is not compatible with this specification's performance requirements and MUST be treated as a backend dependency to resolve during planning, not silently worked around in the frontend.
- Every write this workspace performs that constitutes a decision of record (verification, override, escalation) MUST map to an existing, auditable backend operation that itself satisfies Constitution Principle VIII — this specification does not introduce any decision-recording pathway that bypasses the platform's existing audit-event mechanism.
- Search MUST be backed by a query capability that can rank and filter on borrower name, loan number, and LOS reference at the full portfolio scale within the stated performance targets; if the current backend cannot yet do this performantly, that gap MUST be captured explicitly as a dependency for the implementation plan, not silently absorbed by client-side filtering of partial data (which would violate the "remains responsive at 100,000+ applications" requirement).
- Real-time or near-real-time delivery (notifications, live status updates, background refresh) MUST be treated as a defined contract (a maximum latency, per Success Criteria) that the implementation plan must satisfy via whatever mechanism (polling, push, streaming) meets it — this specification is agnostic to which, but is not agnostic to the latency guarantee itself.

---

## Caching Strategy

- Reference or rarely changing data (e.g., a completed, closed application's evidence and audit history) MAY be cached aggressively and long-lived, since it will not change.
- Actively worked, in-flux data (an application currently under review, a queue the user is actively filtering) MUST be treated as short-lived and revalidated frequently enough that the staleness-indication rule (FR-036) is rarely triggered in normal use.
- Cached data MUST never be presented in a way indistinguishable from confirmed-fresh data when it materially affects a pending decision — see State Management & Data Strategy.
- Client-side caching MUST be scoped per authenticated session and per tenant; no cached data may persist or be reachable across a sign-out/sign-in boundary or across a tenant boundary.

---

## Security Considerations

- Every screen in this workspace displays sensitive personal and financial data; the interface MUST apply data-minimization at the presentation layer — a summary view (e.g., a queue row) MUST show only what is needed to identify and triage the record, deferring full detail to the record view itself (Constitution Principle V, least-data principle).
- The workspace MUST enforce role-appropriate visibility of actions (e.g., an auditor sees no override controls at all, not disabled ones) rather than relying on the user simply not clicking a visible-but-forbidden control.
- Session timeout behavior MUST balance security with the reality of long, focused review sessions: the workspace MUST warn before an inactive session expires and MUST preserve in-progress input across re-authentication (see Forms & Data Entry).
- Any capability to print, export, or copy sensitive data out of the workspace MUST preserve — never strip — the evidentiary provenance (source, page, timestamp) associated with that data.
- Clipboard, screenshot, or export affordances MUST be deliberate, explicit user actions; the interface MUST never auto-populate a clipboard or trigger a silent export of sensitive data as a side effect of another action.

---

## Auditability

- Every verification, override, escalation, and status transition performed through this workspace MUST be visible, in full, from within the product itself — an auditor MUST NOT need database or backend access to reconstruct what happened, when, by whom, and why (Constitution Principle VIII).
- The audit trail view MUST present a strict chronological reconstruction of an application's lifecycle, from ingestion through every subsequent event, in one continuous, readable timeline.
- Every AI-generated finding shown in the audit trail MUST retain and display its attributable model version, prompt version, and policy version at the time it was produced (Constitution Principle XII), even if the platform's current model or policy has since changed.
- The audit trail MUST be presented read-only, with no interface affordance suggesting it can be edited, annotated over, or reordered.

---

## Enterprise UX Guidelines

- **Density over whitespace, without sacrificing clarity.** This is a professional instrument for expert daily users, not a marketing site; favor showing more relevant information per screen (as Bloomberg Terminal, Stripe Dashboard, and Linear do) over generous decorative whitespace, while keeping every element individually legible and well-spaced according to the Spacing System.
- **Every screen answers "where am I, what is this, what can I do" in under one second of orientation** — this is the practical test for information hierarchy on every view in this specification.
- **No modal is used where a persistent, contextual panel would serve** — modals interrupt flow and are reserved for genuinely blocking confirmations (e.g., an irreversible action), never for routine viewing or editing tasks that a docked panel could handle without hiding the surrounding context.
- **The interface never asks the user to remember something across screens** — anything needed for a decision (evidence, prior context, related findings) is surfaced at the point of decision, not left for the user to recall from a previous screen.
- **Consistency of pattern beats novelty of pattern.** A concept (status, confidence, conflict, empty state) is represented exactly the same way everywhere it appears in the product; local creativity in how a given screen represents a shared concept is treated as a defect, not a feature.
- **The product never simulates certainty it does not have.** Confidence indicators, "insufficient evidence" states, and processing/failure states are always honest about what the system does and does not know — this is a direct extension of Constitution Principle III into visual design.

---

## Non-Functional Requirements

- **Scale**: The product MUST be designed against a working assumption of 100,000+ applications, thousands of evidence items per application, and hundreds of documents per application, without degradation to the performance targets defined in Success Criteria.
- **Availability expectation**: The workspace MUST clearly communicate its own degraded or unavailable states (e.g., "search is temporarily degraded") rather than failing silently or presenting stale data as current without indication.
- **Browser/platform support**: The workspace MUST support current versions of major evergreen desktop browsers; support for browsers that cannot meet the accessibility and performance requirements in this specification is explicitly out of scope.
- **Localization readiness**: All user-facing text MUST be externalized from layout in a way that does not assume a fixed string length, even if only one language is supported at initial launch, so that number, date, and currency formats can vary by locale without layout breakage.
- **Internationalized data handling**: Borrower names, addresses, and other free-text fields MUST correctly render non-Latin scripts and unusual-but-valid characters without breaking search, sort, or display.
- **Auditability of the specification itself**: Every requirement in this document is written to be independently testable (see Success Criteria and Acceptance Scenarios); a requirement that cannot be verified without inspecting implementation internals is treated as a defect in this specification, to be corrected before planning begins.

---

## Acceptance Criteria

This specification is considered ready for implementation planning when:

1. Every functional requirement (FR-001 through FR-101) has a corresponding, unambiguous acceptance test derivable from its statement alone, without needing to consult an implementer.
2. Every user story in User Scenarios & Testing has been validated as independently testable and independently valuable, per Spec Kit's incremental-delivery model.
3. Every success criterion is measurable and technology-agnostic, per the Success Criteria Guidelines.
4. No requirement in this document names a specific frontend framework, library, component implementation, or API wire format.
5. The accompanying Specification Quality Checklist (`checklists/requirements.md`) passes in full.

---

## Future Expansion

The following are explicitly out of scope for this specification and are recorded here so they are deliberately deferred, not silently forgotten:

- **Operational Intelligence workspace** for the Mortgage Operations Manager persona: team-wide throughput, SLA aging, and bottleneck analytics across many underwriters, distinct from this specification's single-user Dashboard.
- **Multi-tenant switching** within a single authenticated session, for institutions or deployments that require it.
- **Native mobile companion application** for lightweight review or approval-notification triage away from a desktop.
- **Offline-first operation** for environments with unreliable connectivity.
- **Embedded/iframe deployment mode** allowing the workspace to be surfaced directly within a partner LOS's own interface, consistent with the platform's API-first integration principle (Constitution Principle VI).
- **Portfolio-wide (cross-application) Copilot and analytics**, clearly separated from and never blended with the per-application-scoped Copilot defined in this specification, to preserve AI context isolation guarantees.
- **Voice or dictation input** to the Copilot or to override-reason fields, for hands-busy review scenarios.
- **Configurable, institution-specific Policy Pack-driven UI variation** (e.g., different findings emphasis per regulatory jurisdiction), building on the platform's existing versioned Policy concept.
