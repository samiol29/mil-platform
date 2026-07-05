# Feature Specification: Evidence-Based Product & UX Research Foundation

**Feature Branch**: `004-evidence-based-product-research`

**Created**: 2026-07-05

**Status**: Draft

**Input**: User description: "Evidence-based product research foundation for the Underwriter Workspace and Enterprise Design System: an analysis of the design philosophies behind Stripe Dashboard, Linear, GitHub, Notion, VS Code, Bloomberg Terminal, Figma, ICE Mortgage Technology, Blend, Encompass, Temenos, Finastra, Atlassian, Salesforce, and ServiceNow — extracting principles (not copying appearances), producing cross-product comparisons, and codifying MIL UX Principles, MIL Interaction Principles, MIL Anti-Patterns, and MIL Design Decisions that justify every future frontend and UX decision on the platform. Not implementation, not mockups, not code."

---

## Research Methodology & Scope

This document distinguishes two tiers of evidence, and is explicit about which tier supports each claim, per the instruction to acknowledge limitations rather than invent detail:

**Tier 1 — Directly documented, high confidence.** Stripe, Linear, GitHub, Notion, VS Code, and Figma are developer- and knowledge-worker-facing products with extensive public design writing (engineering/design blogs, public changelogs, conference talks, widely-used and inspectable interfaces). Bloomberg Terminal is unusual in this tier: the product itself is not public, but its design philosophy has been the subject of substantial public commentary, including statements from Bloomberg's own UX design team. Findings for this tier are treated as reliable.

**Tier 2 — Reasoned from aggregated secondary evidence, medium-to-low confidence.** ICE Mortgage Technology (Encompass), Blend, Temenos, Finastra, Atlassian, Salesforce, and ServiceNow are enterprise/regulated-industry products without public UX case studies at the level of detail available for Tier 1. For these, this document reasons from aggregated, independently-corroborated end-user review commentary (G2, TrustRadius, Capterra, Gartner Peer Insights) and vendor materials, retrieved and cited at the time of writing. Where the same complaint or praise recurs independently across multiple, unrelated reviewers, it is treated as directionally reliable industry reputation. Where evidence is thin (Finastra in particular), this is stated plainly rather than compensated for with invented screen-level detail. **No claim in this document asserts a specific, unverified interface detail (a button's location, a specific screen's exact layout) for any Tier 2 product** — claims are limited to what independent reviewers and public materials actually document.

A further, important scope note: **Blend's best-documented UX praise concerns its consumer/borrower-facing application flow, not its loan-officer/underwriter-facing internal tools** — the latter is the far less publicly documented side of its product, and the side actually analogous to MIL's Underwriter Workspace. This document treats that distinction as a finding in its own right, not a gap to paper over.

Sources consulted for Tier 2 findings (retrieved 2026-07-05):

- [Encompass Reviews & Ratings — TrustRadius](https://www.trustradius.com/products/encompass-ellie-mae/reviews)
- [Encompass Digital Mortgage Solution Reviews — G2](https://www.g2.com/products/encompass-digital-mortgage-solution/reviews)
- [Blend Mortgage Suite Reviews — G2](https://www.g2.com/products/blend-mortgage-suite/reviews)
- [How a platform approach to mortgage software improves the LO experience — Blend](https://blend.com/blog/mortgage-suite/platform-approach-mortgage-software-lo-experience/)
- [Temenos Core Reviews — Capterra](https://www.capterra.com/p/111334/TEMENOS-T24/reviews/)
- [Finastra vs Temenos — Gartner Peer Insights](https://www.gartner.com/reviews/market/core-banking-systems/compare/finastra-vs-temenos)
- [ServiceNow Reviews — Capterra](https://www.capterra.com/p/254088/ServiceNow/reviews/)
- [Top ServiceNow IT Service Management Likes & Dislikes — Gartner Peer Insights](https://www.gartner.com/reviews/market/it-service-management-platforms/vendor/servicenow/product/servicenow-service-management/likes-dislikes)
- [How Bloomberg Terminal UX designers conceal complexity — Bloomberg LP](https://www.bloomberg.com/company/stories/how-bloomberg-terminal-ux-designers-conceal-complexity/)

---

## Consumers of This Research (Personas)

### Frontend Engineer / Product Designer

Needs this document to answer, before building or reviewing any new interaction: *has this pattern already been researched, does MIL adopt or reject it, and why?*

### Product Leadership

Needs this document to evaluate a proposed feature or scope change against MIL's established interaction philosophy without re-deriving first principles each time.

### Future Contributor / Auditor

Needs this document, years from now, to understand not just what MIL's UX rules are but the specific evidence and reasoning that produced them — so a proposed exception can be evaluated against the original logic, not just the current rule text.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate a Proposed Interaction Against Prior Research (Priority: P1)

An engineer or designer proposing a new interaction pattern (e.g., "should the notification list support infinite scroll?") checks this document first and finds either an existing, reasoned MIL position (principle, anti-pattern, or design decision) directly applicable to the question, or confirms the question is genuinely novel and needs new research — without redoing product research from scratch each time.

**Why this priority**: This is the entire purpose of the document. If it does not reliably answer real, everyday questions engineers and designers actually have, it has failed regardless of its other qualities.

**Independent Test**: Pose 5 plausible, specific interaction questions not verbatim-covered by the document's own worked examples (e.g., "should evidence conflicts use a modal?") and confirm each can be answered by combining an existing MIL UX Principle, Interaction Principle, or Anti-Pattern entry, with a clear chain of reasoning back to a specific research finding.

**Acceptance Scenarios**:

1. **Given** a proposed interaction pattern, **When** an engineer searches this document for guidance, **Then** they find either a directly applicable MIL Anti-Pattern (if the pattern should be rejected), a MIL Interaction Principle (if the pattern is already governed), or a clear statement that the question is novel.
2. **Given** a MIL UX Principle or Anti-Pattern entry, **When** its stated rationale is inspected, **Then** it cites a specific product research finding earlier in the document, not an unsupported assertion.
3. **Given** two MIL Principles could both plausibly apply to the same design question in tension (e.g., Keyboard First vs. Progressive Disclosure), **When** this is checked against the document, **Then** the document's principles include enough specificity (or a named precedence/reconciliation note) to resolve the tension rather than leaving it ambiguous.

---

### User Story 2 - Audit a Design for Anti-Pattern Reintroduction (Priority: P1)

A designer, before finalizing a new screen, checks it against the MIL Anti-Patterns list and catches an accidental reintroduction of a previously-rejected pattern (e.g., a modal used for routine editing, a rainbow-coded status scheme) before it reaches implementation.

**Why this priority**: Design systems and principles decay when nothing forces a check against them at the point of new design work; this is the practical mechanism that prevents drift.

**Independent Test**: Present a designer with a draft screen containing one deliberately reintroduced anti-pattern (e.g., a full-screen modal used for a routine evidence-review task) and confirm the Anti-Patterns list, checked directly against the screen, catches it.

**Acceptance Scenarios**:

1. **Given** a draft screen using a blocking modal for a non-blocking, routine task, **When** checked against the MIL Anti-Patterns list, **Then** the relevant entry (modal abuse) is found and its rationale explains why a drawer/panel is required instead.
2. **Given** a draft screen introducing a new status color outside the Design System's semantic token set, **When** checked against this document, **Then** the "rainbow status colors" anti-pattern and the Design System's closed-token requirement are both found and cross-referenced.

---

### User Story 3 - Understand the Reasoning Behind an Existing MIL Decision (Priority: P2)

A new team member or stakeholder unfamiliar with why MIL rejected a specific, plausible-sounding UX approach (e.g., "why isn't the Copilot a full-screen chat like ChatGPT?", "why not just copy Bloomberg's density approach wholesale?") finds a specific Design Decision record stating the decision, the reasoning, the alternative that was genuinely considered, why it was rejected, and the long-term implication of the choice.

**Why this priority**: Undocumented rationale is re-litigated repeatedly by each new stakeholder; a recorded decision, once made well, should not need to be re-argued from scratch.

**Independent Test**: Ask a plausible "why didn't we just do X" question about an already-established MIL position and confirm a specific MIL Design Decision entry answers it with a real, specific rejected alternative (not a strawman) and a stated long-term consequence.

**Acceptance Scenarios**:

1. **Given** the question "why not build the Copilot as a full-screen chat interface," **When** checked against this document, **Then** a specific Design Decision entry names that exact alternative, explains why it was rejected, and cites the specific research finding (GitHub Copilot's and VS Code's contextual, non-full-screen AI placement) supporting the rejection.
2. **Given** the question "why not copy Bloomberg Terminal's UI more directly, since it's held up as an inspiration," **When** checked against this document, **Then** a specific Design Decision entry explains that Bloomberg's density is inseparable from a multi-month training expectation MIL's own success criteria rule out, and states what MIL adopts instead (discoverable density, not memorized density).

---

### User Story 4 - Scope a New Feature Against MIL's Interaction Philosophy (Priority: P2)

Product leadership evaluating a proposed new feature or workspace (e.g., a future Operational Intelligence dashboard) uses this document's cross-product comparisons and principles to make an early scoping call — what density, what navigation model, what AI placement is appropriate — without commissioning fresh product research for every new feature.

**Why this priority**: This is a lower-frequency but high-leverage use of the document; getting early scoping calls right prevents expensive rework later.

**Independent Test**: Apply this document's principles to a stated hypothetical feature (a future team-wide analytics dashboard) and confirm a directionally clear, reasoned scoping recommendation can be produced using only this document.

**Acceptance Scenarios**:

1. **Given** a hypothetical future analytics-heavy feature, **When** evaluated against this document's Data Visualization findings and MIL UX Principles, **Then** a specific, reasoned recommendation (e.g., reuse the existing constrained data-viz palette, do not introduce a new charting visual language) can be produced directly from the document.

---

### Edge Cases

- **A researched product materially redesigns after this document is written**: this document's findings are dated (2026-07-05) and describe the products as understood at that time; a future contributor relying on a specific claim about a fast-moving Tier 1 product should verify it has not since changed, particularly for AI-feature-related claims, which are the most likely to change quickly across this entire research set.
- **A future feature has no analogous pattern in any researched product**: this document does not claim exhaustive coverage of all possible UX questions; where no principle, anti-pattern, or design decision applies, this is itself a valid, statable outcome ("this is genuinely novel; new research is warranted"), not a failure of the document.
- **Two MIL Principles appear to conflict for a specific case**: see Part III's explicit precedence guidance (Evidence First and Human in Control take precedence over Performance is a Feature and Keyboard First wherever they would otherwise conflict — speed and shortcuts must never be purchased at the cost of evidence traceability or human authority).
- **A stakeholder wants to adopt a pattern this document lists as an anti-pattern, for a specific, argued exception**: the Future Extensibility process defined in the Design System specification (003) governs this — a proposed exception must be evaluated in writing against this document's original reasoning, not simply overridden by preference.
- **Tier 2 evidence for a specific product later proves to be unrepresentative or outdated** (e.g., a vendor materially improves a criticized product): this document's Tier 2 findings are explicitly lower-confidence and reasoned from aggregated review commentary as of the stated retrieval date; they should be revisited if a specific Tier 2 finding becomes load-bearing for a major future decision.

---

## Requirements *(mandatory)*

### Functional Requirements

#### A. Research Coverage & Rigor

- **FR-001**: This document MUST research and document all 15 named products (Stripe Dashboard, Linear, GitHub, Notion, VS Code, Bloomberg Terminal, Figma, ICE Mortgage Technology, Blend, Encompass, Temenos, Finastra, Atlassian, Salesforce, ServiceNow) across the 20 requested dimensions, or explicitly state that a given dimension is not applicable to or not derivable for a specific product, rather than fabricating a plausible-sounding but unverified answer.
- **FR-002**: Where ICE Mortgage Technology and Encompass refer to the same underlying product, this document MUST state that explicitly rather than manufacturing artificially distinct findings for both.
- **FR-003**: For every product where direct, hands-on product access or detailed public UX documentation is unavailable (Tier 2, per Research Methodology), this document MUST explicitly acknowledge that limitation and reason only from cited, aggregated secondary evidence — it MUST NOT assert a specific, unverifiable interface detail as though independently confirmed.
- **FR-004**: Every substantive claim about a Tier 2 product MUST be traceable to a cited source consulted for this document.
- **FR-005**: Where available evidence for a product is particularly thin (e.g., Finastra), this document MUST state that explicitly and treat conclusions drawn from it as lower-confidence than better-evidenced entries, rather than presenting all products with uniform apparent confidence.

#### B. Product Dossier Content

- **FR-006**: For every researched product, this document MUST document: primary users, main workflow, navigation philosophy, information hierarchy, search experience, data density, keyboard workflow, tables, forms, filtering, document viewing, multi-panel layouts, performance philosophy, accessibility, AI integration (where applicable), strengths, weaknesses, what MIL should adopt, what MIL should avoid, and trade-offs.
- **FR-007**: Every "what MIL should adopt" and "what MIL should avoid" entry MUST state a specific reason tied to a specific finding for that product, not a generic or interchangeable justification that could apply equally to any other product.
- **FR-008**: Every "trade-offs" entry MUST identify at least one genuine cost or limitation of adopting that product's pattern for MIL specifically, even where the overall recommendation is to adopt it.

#### C. Cross-Product Comparison

- **FR-009**: This document MUST produce named cross-product comparisons addressing, at minimum, the specific comparative questions posed in the original research brief (Stripe vs. Linear; why Bloomberg is expert-optimized; why GitHub is easy to scan; why VS Code scales; why Figma's panel system works; why enterprise CRMs often feel slow), each with a specific, evidence-grounded answer.
- **FR-010**: Cross-product comparisons MUST draw explicit, named connections to MIL's own design decisions where relevant, not remain purely descriptive of the compared products in isolation.

#### D. MIL UX Principles

- **FR-011**: This document MUST define a named, finite set of MIL UX Principles, each stated as an actionable rule (not a vague aspiration), each with a rationale citing specific product research findings from this document.
- **FR-012**: Where two MIL UX Principles could plausibly conflict for a given design question, this document MUST state which takes precedence and why.

#### E. MIL Interaction Principles

- **FR-013**: This document MUST define MIL Interaction Principles covering, at minimum: navigation, searching, reviewing evidence, reviewing documents, Copilot interaction, tables, filtering, loading, error handling, notifications, and focus management.
- **FR-014**: Every MIL Interaction Principle MUST be consistent with (not merely coexist alongside) the requirements already established in the Underwriter Workspace specification (002) and the Enterprise Design System specification (003); any point of tension discovered during this research MUST be explicitly flagged and reconciled, not silently ignored.

#### F. MIL Anti-Patterns

- **FR-015**: This document MUST define a named set of MIL Anti-Patterns, each including: the pattern's name, why it is rejected, a real product/context exemplifying the problem where one exists in this research, and what MIL does instead.
- **FR-016**: Anti-Patterns MUST include, at minimum, the patterns named in the original research brief (infinite scrolling everywhere, ChatGPT-style full-screen chat, hidden navigation, consumer-style animations, dashboard overload, rainbow status colors, modal abuse, UUID-first workflows, decorative AI, generic admin-template layouts), and MAY include additional patterns this research specifically surfaces.

#### G. MIL Design Decisions

- **FR-017**: This document MUST record MIL Design Decisions for every major, non-obvious UX choice already made or reinforced by this research, each including: the decision, the reason, a genuinely considered alternative, why that alternative was rejected, and the long-term implication of the choice.
- **FR-018**: At least one MIL Design Decision MUST directly address the tension between adopting a researched product's celebrated strength and a specific, real cost of that strength that MIL's own constraints make unacceptable (e.g., Bloomberg Terminal's density versus its multi-month training expectation) — this document MUST NOT present any researched product as an uncomplicated model to copy.

#### H. Traceability & Governance

- **FR-019**: Every MIL UX Principle, Interaction Principle, Anti-Pattern, and Design Decision MUST be traceable to at least one specific finding documented earlier in this same document — no principle, anti-pattern, or decision may rest solely on unsupported assertion.
- **FR-020**: This document MUST NOT contain implementation detail — no frontend framework, library, specific color value, or component code; it defines research findings and resulting product/UX rules, consistent with the Enterprise Design System specification's own separation of rules from implementation.
- **FR-021**: Where a finding in this document refines, sharpens, or reveals a gap in an assumption already made in the Underwriter Workspace specification (002) or Enterprise Design System specification (003), this document MUST state that explicitly rather than silently diverging or silently duplicating.

### Key Entities *(include if feature involves data)*

- **Product Research Dossier**: A structured record for one researched product, covering all 20 requested dimensions, an evidence tier (1 or 2), and adopt/avoid/trade-off conclusions.
- **Cross-Product Comparison**: A named, evidence-grounded contrast between two or more products, with an explicit implication for MIL.
- **MIL UX Principle**: A named, actionable product law, with a stated rationale tied to specific research findings and, where relevant, a stated precedence relative to other principles.
- **MIL Interaction Principle**: A category-specific interaction rule (e.g., for tables, for filtering) consistent with and elaborating on the MIL UX Principles.
- **MIL Anti-Pattern**: A named, explicitly rejected pattern, with its rationale, a real exemplar where available, and MIL's stated alternative.
- **MIL Design Decision**: A recorded decision with its reason, a genuinely considered alternative, why that alternative was rejected, and its long-term implication.
- **Evidence Tier**: A confidence classification (Tier 1: directly documented; Tier 2: reasoned from aggregated secondary evidence) attached to every product dossier and, implicitly, to every conclusion drawn from it.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A proposed new frontend interaction pattern can be checked against this document's Anti-Patterns and Principles to determine whether it has already been considered and resolved, in under 5 minutes, for at least 90% of realistic scenarios tested.
- **SC-002**: 100% of MIL UX Principles, Interaction Principles, and Anti-Patterns cite at least one specific, earlier-documented research finding as supporting evidence — zero rest on unsupported assertion.
- **SC-003**: 100% of MIL Design Decisions name a specific, genuinely considered alternative (not a strawman) and a specific reason for its rejection.
- **SC-004**: A new team member, given only this document, correctly predicts MIL's stance on a novel-but-analogous UX question (e.g., "should the notification list use infinite scroll?") without further guidance, verified by review, in at least 90% of test cases.
- **SC-005**: Zero claims in this document assert an unverifiable, specific interface detail for a Tier 2 product; every Tier 2 claim traces to a cited source.
- **SC-006**: Every point of tension discovered between this research and the existing Underwriter Workspace (002) or Enterprise Design System (003) specifications is explicitly resolved or flagged within this document — none are silently left unreconciled.

---

## Assumptions

- **This document is a research and rationale artifact, not a specification of new product scope.** It does not introduce new functional requirements beyond those already established by the Underwriter Workspace (002) and Enterprise Design System (003) specifications; where it recommends a specific pattern, that recommendation is understood to operate within the boundaries those two specifications already set.
- **The evidence tiering (Tier 1 / Tier 2) is a permanent, load-bearing feature of this document, not a temporary caveat.** Future readers should continue to weight Tier 2 conclusions about mortgage-specific and general enterprise software accordingly, rather than treating this document's confident tone elsewhere as uniform across all entries.
- **This document's findings are current as of 2026-07-05.** Fast-moving areas — especially AI-feature placement across every researched product — should be expected to change; the principles this document extracts (e.g., "AI stays anchored to context, not a separate destination") are intended to be durable even if the specific product features that inspired them evolve.
- **Public review-aggregation platforms (G2, TrustRadius, Capterra, Gartner Peer Insights) are treated as a legitimate, if imperfect, evidence source for enterprise software UX reputation** — independently corroborated, recurring complaints across many unrelated reviewers are treated as meaningful signal, consistent with how this kind of aggregated evidence is generally used in industry and product research practice.
- **"Enterprise CRM" and "core banking" products (Salesforce, ServiceNow, Atlassian, Temenos, Finastra) are included for their general enterprise-UX lessons, not because they are functionally analogous to MIL.** Their primary research value in this document is as cautionary evidence about configurability, navigational drift, and performance decay at scale — not as products MIL should resemble.

---

# Part I — Product Research Dossiers

## Group A: Enterprise Software (Tier 1 — Directly Documented)

### Stripe Dashboard

| Dimension | Finding |
|---|---|
| Primary users | Developers, finance/ops teams, support agents investigating payments and disputes |
| Main workflow | Monitor transactions, investigate a specific payment/customer, resolve disputes, configure billing |
| Navigation | Flat top-level sidebar, no deep nesting; global Cmd/Ctrl-K search as a first-class navigation method |
| Information hierarchy | Strong visual weight on the primary number (amount, status); metadata deliberately de-emphasized via muted type/color |
| Search | Global search across objects (customers, charges, invoices) by human-meaningful identifiers; raw IDs remain visible/copyable for API cross-reference but are not the primary label |
| Data density | Moderate-to-high; dense tables with disciplined, not wasteful, row spacing |
| Keyboard workflow | Cmd-K first-class; many list/detail flows are keyboard-navigable |
| Tables | Sortable, filterable, sticky headers, consistent monospaced treatment for IDs and amounts |
| Forms | Inline validation, minimal steps, advanced options behind explicit progressive disclosure |
| Filtering | Structured filter builder (field + operator + value), not free-text-only |
| Document viewing | No general document viewer; closest analogue is inline invoice/receipt preview rendered in place, not download-first |
| Multi-panel layouts | Slide-over panels for viewing a related record (e.g., a customer from within a payment) without losing place |
| Performance philosophy | Fast; optimistic UI for low-risk settings changes, server-confirmed for money-moving actions |
| Accessibility | Documented WCAG commitment; strong contrast defaults; solid keyboard operability given its developer-heavy audience |
| AI integration | Emerging (fraud/risk explanation features) but not central to the dashboard's core identity |

**Strengths**: trustworthy restraint; information hierarchy that never buries the number that matters; the slide-over panel as a genuinely reusable "view related record without losing context" pattern.
**Weaknesses**: some advanced configuration areas (tax, billing rules) remain dense/technical even for non-developer finance users; visible seams between older and newer redesigned sections during migration periods.
**What MIL should adopt**: the slide-over/side-panel pattern for inspecting a related record in context; Cmd-K global search; a structured filter builder; monospaced numeric/financial-value treatment (already reflected in Design System FR-007).
**What MIL should avoid**: nothing significant from Stripe itself requires avoidance; the caution is about audience, not pattern (see Trade-offs).
**Trade-offs**: Stripe can assume a technically fluent audience (developers); MIL cannot assume the same fluency across all its personas (e.g., compliance/audit reviewers), so patterns borrowed from Stripe must be presented with less assumed technical vocabulary than Stripe itself uses.

---

### Linear

| Dimension | Finding |
|---|---|
| Primary users | Software engineers and product teams managing issues and projects |
| Main workflow | Triage issues, move them through a workflow, rapid keyboard-driven entry and updates |
| Navigation | Minimal sidebar; the command palette is the *primary*, not secondary, navigation method |
| Information hierarchy | Extremely restrained; status/priority conveyed via small, consistent iconography rather than heavy color blocking |
| Search | Instant, fuzzy, keyboard-first, search-as-you-type with no explicit submit step |
| Data density | High but airy, achieved through a disciplined spacing scale rather than sparse whitespace |
| Keyboard workflow | Best-in-class in this entire research set; nearly every action has a discoverable shortcut |
| Tables | List views behave like compact, keyboard-navigable rows (list-style, not grid-style, tables) |
| Forms | Inline, edit-in-place wherever possible; full-page or modal forms are rare |
| Filtering | Composable filter chips saved as named "Views" — a central product concept, not a bolted-on feature |
| Document viewing | Not applicable; Linear is not a document-centric product |
| Multi-panel layouts | Single-pane-primary with one contextual detail panel; deliberately avoids more than two panes to prevent split attention |
| Performance philosophy | Explicitly optimistic UI everywhere, stated as a design value ("feel like a local app") |
| Accessibility | Strong keyboard support as a natural consequence of its keyboard-first philosophy; contrast and dark theme well executed |
| AI integration | AI-assisted triage/summarization added as subordinate to the core fast manual workflow, not chat-first |

**Strengths**: motion discipline; keyboard completeness; saved views as a first-class concept; exceptional perceived speed.
**Weaknesses**: its blanket-optimistic-UI philosophy is safe specifically because issue-tracking data is low-stakes and reversible — a real, important limitation that does not transfer to a regulated, audit-critical domain.
**What MIL should adopt**: command palette as primary navigation; saved views as a core concept (already reflected in Workspace FR-020); restrained iconographic status signaling; the two-pane-maximum discipline.
**What MIL should avoid**: blanket optimistic UI — MIL must remain selective, exactly as already established in the Design System specification's optimistic-UI policy.
**Trade-offs**: Linear's domain (low-stakes, reversible issue data) affords maximal optimism; MIL's domain (regulated, audit-critical decisions) cannot copy this wholesale without violating Constitution Principle VIII — this is one of the clearest examples in this research of a celebrated pattern that must be adopted only partially.

---

### GitHub

| Dimension | Finding |
|---|---|
| Primary users | Developers, reviewers, maintainers |
| Main workflow | Review a proposed change (diff), discuss it inline, trace history, merge |
| Navigation | Consistent tab structure within a repository (Code/Issues/Pull Requests/Actions), identical across every repo |
| Information hierarchy | Diff-centric; the change is always the visual focus, discussion is secondary and anchored to specific lines |
| Search | Global and scoped search supporting structured qualifiers (`is:open label:bug`) while remaining usable as plain text |
| Data density | High in diffs/code, moderate in discussion surfaces |
| Keyboard workflow | Strong list navigation (j/k-style) and single-letter shortcuts, discoverable via a "?" help overlay |
| Tables | Issue/PR lists are simple, scannable, label- and status-forward |
| Forms | Markdown-first, inline, minimal chrome |
| Filtering | A de facto structured query language (search qualifiers) surfaced through an approachable search bar |
| Document viewing | The diff viewer's line-anchored, exact-location comment pattern is the closest public analogue to MIL's evidence-to-document anchoring need |
| Multi-panel layouts | Primarily single-column with anchored inline expansion (comments open in place), rather than a separate pane |
| Performance philosophy | Fast initial paint even for very large diffs via lazy-loading/pagination of large files |
| Accessibility | Long-documented, mature program (GitHub's Primer design system publishes explicit accessibility guidance) |
| AI integration | Copilot is contextual and dismissible (inline suggestions, PR summaries) — never a mandatory full-screen chat takeover |

**Strengths**: the line/region-anchored annotation pattern is the single best public analogue to MIL's own evidence-highlighting requirement; structured-but-approachable search; mature accessibility practice; contextual, non-intrusive AI placement.
**Weaknesses**: even GitHub's own UI can feel sluggish at extreme scale (very large monorepos/diffs) — an honest reminder that no researched pattern scales for free at any size.
**What MIL should adopt**: line/region-anchored evidence highlighting (already central to Workspace FR-040 and Design System FR-058); structured-but-friendly search qualifiers; a "?"-style shortcut-discovery overlay; contextual, dismissible AI (directly reinforcing MIL's application-anchored Copilot decision).
**What MIL should avoid**: nothing major; GitHub is one of the strongest positive analogues in this entire research set.
**Trade-offs**: GitHub's anchoring pattern assumes one fairly linear artifact (a code file); MIL must adapt the same idea to multi-page PDFs and multiple heterogeneous document types, a harder rendering problem GitHub never had to solve.

---

### Notion

| Dimension | Finding |
|---|---|
| Primary users | Knowledge workers organizing flexible, mixed-type content |
| Main workflow | Create and organize a flexible document/database hybrid, switching between "page" and "database" views of the same data |
| Navigation | Deep, nested sidebar (pages within pages) — notably the one product in this set that uses hierarchical nesting successfully, because content organization, not task-execution speed, is the point |
| Information hierarchy | Content-driven and flexible; the product enforces less structure than the user's own organization does |
| Search | Global quick-find plus in-page search; increasingly AI-assisted workspace-wide question answering |
| Data density | Deliberately low-to-moderate; generous whitespace is a core part of Notion's identity, a sharp contrast to Bloomberg/Linear |
| Keyboard workflow | Strong slash-command pattern for inserting structured content inline; less exhaustive than Linear's full navigational keyboard completeness |
| Tables | Multiple views (table, board, calendar, gallery) of the same underlying database — Notion's single most transferable idea |
| Forms | Inline, freeform property editing; editing a database row feels like editing a document, not filling a form |
| Filtering | Per-view saved filter/sort/grouping, conceptually identical to Linear's saved views but applied to flexible content |
| Document viewing | Its core content model *is* the document; content blocks load progressively — a lightweight, genuine lazy-load pattern, but for content blocks, not tabular records (an important nuance versus "infinite scroll on a queue") |
| Multi-panel layouts | Primarily single-pane with peek/preview panels for linked pages |
| Performance philosophy | Historically and repeatedly criticized for perceptible lag on very large or complex pages — a documented, honest weakness |
| Accessibility | Adequate but not best-in-class relative to this set; flexible/nested structure creates real keyboard- and screen-reader-navigation complexity |
| AI integration | "Notion AI" is invoked contextually (highlight text → ask AI) rather than offered as a persistent separate chat surface |

**Strengths**: multiple views over one dataset; on-demand, text-anchored AI invocation; density flexibility where flexibility is genuinely valuable.
**Weaknesses**: documented performance degradation on very large pages; its low-density defaults and nested-page navigation are both directly unsuitable for MIL's expert-density, flat-navigation needs.
**What MIL should adopt**: multiple views of one underlying dataset (directly applicable to the Application Queue, e.g., a future kanban-by-stage view alongside the default table view); on-demand, text-anchored AI invocation.
**What MIL should avoid**: deep nested-page navigation (directly contradicts the flat, command-palette-first navigation already committed to in Workspace FR-001–002); low-density defaults; its documented large-page performance ceiling, unacceptable at MIL's stated 100,000+ record scale.
**Trade-offs**: Notion trades performance headroom for content flexibility; MIL's scale requirements make that specific trade unaffordable.

---

### VS Code

| Dimension | Finding |
|---|---|
| Primary users | Software developers, all day, every day |
| Main workflow | Navigate a large file tree, edit, run, and debug within one persistent workspace |
| Navigation | The command palette as a universal fallback for any action, alongside a persistent, collapsible sidebar |
| Information hierarchy | Minimal chrome; content occupies nearly all screen space, tools recede until summoned |
| Search | Fuzzy file search ("Quick Open") and full-text project search, both keyboard-first and near-instant even in huge codebases |
| Data density | Very high and fully user-configurable; density is a user preference, not a fixed system decision |
| Keyboard workflow | The reference standard in this entire research set; almost nothing requires a mouse |
| Tables | Not applicable directly, but every list-like surface (search results, file trees) follows identical keyboard-navigation conventions |
| Forms | Minimal traditional forms; configuration is a searchable settings UI backed by a structured, itself-searchable schema |
| Filtering | Search-scoped filtering (file type, folder, exclude patterns) via structured, discoverable syntax |
| Document viewing | Multi-tab, split-pane editing; a pinned-vs-preview tab distinction prevents tab overload |
| Multi-panel layouts | The best-documented reference for a serious multi-pane workspace (sidebar, editor, panel, status bar) that scales from one small file to an enormous enterprise monorepo without redesign |
| Performance philosophy | Explicitly engineered for perceived instantness; virtualized rendering everywhere large lists/files are involved — the direct precedent for MIL's own virtualized-table requirement |
| Accessibility | Mature, actively maintained program (screen-reader mode, high-contrast themes, full keyboard operability), reflecting enterprise/government adoption requirements |
| AI integration | Copilot is inline, dismissible, and contextual — never a mandatory or default full-screen takeover; a second strong precedent, alongside GitHub, for MIL's application-anchored Copilot decision |

**Strengths**: the strongest, most complete precedent in this entire research set for an expert multi-pane workspace that scales; command palette as universal fallback; non-intrusive AI.
**Weaknesses**: its extensibility model (thousands of third-party extensions) creates real, documented per-user inconsistency risk — not directly relevant to MIL (a closed, non-extensible product), but a useful reason MIL's own component library must remain closed (Design System FR-078–081).
**What MIL should adopt**: command palette as universal fallback (Workspace FR-002); virtualized rendering as a default assumption, not a later optimization (Workspace FR-017, Performance Strategy); pinned-vs-preview tab discipline for the Document Viewer; contextual, dismissible AI.
**What MIL should avoid**: nothing significant; of every product researched, VS Code's discipline maps onto MIL's actual technical requirements most directly of all.
**Trade-offs**: none significant to name; this is the closest positive analogue in the entire research set.

---

### Bloomberg Terminal

| Dimension | Finding |
|---|---|
| Primary users | Financial traders and analysts, extensively and often formally trained/certified |
| Main workflow | Rapid retrieval of market data via short command codes, cross-referencing many data feeds simultaneously |
| Navigation | Command-line-style function codes rather than discoverable menus — deliberately, and this is the single most important fact to understand before borrowing anything from Bloomberg |
| Information hierarchy | Extreme density, small text, many simultaneous panels/windows, optimized for a user who already knows exactly what they want |
| Search | A structured command syntax — closer to a domain-specific query language than to a search bar |
| Data density | The highest in this entire research set, by a wide margin |
| Keyboard workflow | Total; the keyboard, including a specialized physical keyboard with dedicated function keys, is the primary and sometimes only interface |
| Tables | Extremely dense, real-time-updating grids; monospaced numeric alignment is a hard requirement |
| Forms | Minimal in the traditional sense; input is command-based, not form-based |
| Filtering | Expressed via command parameters, not visual filter builders |
| Document viewing | Not applicable in the traditional sense; Bloomberg is data/market-feed centric, not document-centric |
| Multi-panel layouts | Many simultaneous windows is the entire paradigm; users are trained to manage their own multi-monitor, multi-window workspace |
| Performance philosophy | Real-time and uncompromising; latency is treated as a trading risk, not merely a UX inconvenience |
| Accessibility | Not a strong public reference point for modern web-accessibility standards; its enterprise financial-firm procurement model has not historically prioritized this the way MIL's own regulatory context requires |
| AI integration | Increasingly adds natural-language query features **on top of**, not as a replacement for, its expert command layer — notably, as an accommodation for less-expert users, not a redesign of the core |

**Strengths**: proof that extreme density and speed are achievable and genuinely valued by expert users under real time pressure — a legitimate existence proof for MIL's own density-over-whitespace stance.
**Weaknesses (well-documented, not a MIL assumption)**: Bloomberg's own UX design team has publicly described their job as concealing decades of accumulated complexity, not eliminating it; independently reported accounts describe a 3–6 month learning curve to reach practical proficiency. This is the single most important trade-off finding in this entire research document.
**What MIL should adopt**: information density as a legitimate, deliberate choice for expert daily users; monospaced/tabular numeric discipline (already reflected in Design System typography rules); real-time update expectations for live/queue data.
**What MIL should avoid**: command-memorization as the primary interaction model; sacrificing control discoverability for density; any assumption of a multi-month training period.
**Trade-offs (the central tension in this entire document)**: MIL wants Bloomberg's density and speed but cannot and must not adopt the mechanism Bloomberg uses to achieve them (opaque, memorized commands plus months of training) — this directly conflicts with the Underwriter Workspace specification's own SC-006 (a new underwriter productive in under 15 minutes, no external training). MIL's equivalent of Bloomberg's command layer must be **discoverable**: a fuzzy-searchable, suggestion-driven command palette visible from a single keystroke, not a memorized mnemonic system. See Design Decision "Density Without Opacity" in Part VI.

---

### Figma

| Dimension | Finding |
|---|---|
| Primary users | Designers, increasingly cross-functional teams (PM, engineering) as reviewers/commenters |
| Main workflow | Manipulate a visual canvas, organize objects via layers/panels, collaborate in real time |
| Navigation | Persistent left (layers/pages) and right (properties) panels flanking a central canvas |
| Information hierarchy | The canvas is primary; panels adapt their content to whatever is currently selected, never showing irrelevant properties |
| Search | Layer/component search within a file; broader team-library search across shared components |
| Data density | High but selection-scoped — Figma shows only properties relevant to the current selection, a strong, transferable discipline |
| Keyboard workflow | Extensive shortcuts for canvas manipulation; more direct-manipulation-first with keyboard acceleration layered on, less command-palette-first than Linear/VS Code |
| Tables | Not applicable directly (canvas-based), though component/variant management increasingly resembles structured data management |
| Forms | Property panels function as always-visible, context-sensitive forms rather than separate modal forms |
| Filtering | Layer-panel search/filtering by name or type |
| Document viewing | Not applicable directly |
| Multi-panel layouts | The best public reference for context-sensitive side panels that change content based on selection without ever losing the primary canvas — directly relevant to MIL's Evidence Explorer/Document Viewer relationship |
| Performance philosophy | Real-time multiplayer rendering at low latency is a core, heavily engineered value proposition |
| Accessibility | A documented, ongoing area of investment and public criticism — canvas-based, freeform tools are inherently harder to make screen-reader accessible than document/table-based ones, an industry-wide challenge, not unique to Figma |
| AI integration | Emerging generative features invoked contextually from a selection, not as a separate persistent chat mode |

**Strengths**: selection-scoped, always-relevant side panels; strong real-time collaborative performance engineering.
**Weaknesses**: canvas-based accessibility limitations are a well-documented, category-wide challenge — directly informing MIL's decision to remain a structured, document/table-based interface, which is the more accessible architectural choice, not a compromise.
**What MIL should adopt**: selection-scoped side panels showing only what's relevant to the current context — directly maps to the Evidence Explorer showing only the selected item's relationships (Workspace FR-064, FR-066).
**What MIL should avoid**: canvas-based freeform interaction as a primary pattern; more importantly, this is a reminder that MIL's structured, table/document-based architecture is an accessibility *advantage* to be preserved deliberately, not an inherited limitation.
**Trade-offs**: Figma's real-time multiplayer engineering investment is substantial and specific to true concurrent canvas editing; MIL's concurrency needs (soft conflict detection, per Workspace FR-036) are comparatively lighter and already correctly scoped down.

---

## Group B: Mortgage / Financial Software (Tier 2 — Reasoned from Aggregated Evidence)

### ICE Mortgage Technology (Encompass)

*Note (FR-002): "ICE Mortgage Technology" and "Encompass" refer to the same underlying flagship loan origination system (Encompass is ICE Mortgage Technology's core LOS product); this dossier treats them as one entry rather than manufacturing artificially distinct findings.*

| Dimension | Finding (Tier 2 — aggregated review evidence) |
|---|---|
| Primary users | Loan officers, processors, underwriters, and closers — the full LOS back-office staff at banks and large lenders |
| Main workflow | Move a loan file through a highly configurable, forms-heavy pipeline from application to closing |
| Navigation | Reviewers describe the interface as dense and "antiquated," with difficulty locating things |
| Information hierarchy | Not a documented strength; reviewers specifically cite confusing field naming and difficulty finding the right field or screen |
| Search | Reviewers specifically report needing to reset the pipeline, loan folder, and view just to search for old or denied loans — a direct, real-world cautionary tale |
| Data density | High, but associated by reviewers with clutter rather than clarity — a meaningful contrast to Bloomberg's disciplined density |
| Keyboard workflow | Not documented as a notable strength or focus area |
| Tables | Pipeline/loan-list views exist but reviewers describe needing repeated manual reconfiguration to find things, rather than reliable persistent saved views |
| Forms | The dominant interaction paradigm; reviewers describe field-level quirks (e.g., moved fields not persisting) |
| Filtering | Present but apparently insufficient to prevent the documented "reset pipeline to search" complaint |
| Document viewing | Central to the product but not specifically praised for its viewing experience in available reviews |
| Multi-panel layouts | Not a documented strength |
| Performance philosophy | Specifically and repeatedly criticized: no autosave, described by reviewers as risky given the potential to lose hours of work; documented printing issues and crashes |
| Accessibility | Not a notable area of public documentation either way |
| AI integration | Recent AI/automation investment layered onto a much older core UI, not a native design principle |

**Strengths (per available evidence)**: extensive functionality and integration breadth; deep configurability; an entrenched, trusted position with large lenders.
**Weaknesses (per available evidence)**: dated interface, steep learning curve requiring formal training, no autosave (a severe, specific, and repeatedly documented risk), state loss triggered by searching, confusing field naming, crash-proneness.
**What MIL should adopt**: nothing directly from Encompass's UX execution — its users' own complaints instead validate, by direct negative example, requirements MIL has already established: preserving in-progress input across interruption (Workspace FR-077), never losing filter/view state as a side effect of navigating or searching (Workspace FR-004), and treating graceful save/retry as non-negotiable (Workspace FR-034).
**What MIL should avoid**: form-first navigation as the dominant paradigm; losing view or filter state as a side effect of search; treating autosave and data preservation as optional rather than foundational.
**Trade-offs / limitation of this assessment**: built from aggregated end-user review commentary and industry reputation, not a firsthand usability audit — treated as directionally reliable because the same specific complaints (no autosave, lost search state) recur independently across multiple, unrelated reviewers, but not a substitute for formal usability research.

---

### Blend

*Note (Research Methodology): the best-documented part of Blend's UX praise concerns its consumer/borrower-facing application flow, not its loan-officer/underwriter-facing internal tools — the latter is the side actually analogous to MIL's Underwriter Workspace, and is far less publicly documented. This dossier treats that gap as a finding in its own right.*

| Dimension | Finding (Tier 2 — aggregated review evidence) |
|---|---|
| Primary users (documented side) | Borrowers, in a self-service digital mortgage application |
| Primary users (less documented side) | Loan officers/processors using Blend as an internal system of work |
| Main workflow (documented side) | A guided, conversational, single-flow mortgage application surfacing only relevant questions |
| Navigation | Not deeply documented for the internal/back-office side; the consumer flow is deliberately linear/wizard-style, appropriate for a one-time task, not an expert doing dozens of reviews a day |
| Information hierarchy | Consumer flow specifically praised for showing only relevant questions — a genuinely transferable progressive-disclosure principle |
| Search | Not a meaningful concept in the documented consumer flow |
| Data density | Deliberately low, appropriate to a one-time consumer task — explicitly not analogous to MIL's daily-expert-tool density needs |
| Keyboard workflow | Not a documented focus (consumer, largely mobile-first usage) |
| Tables | Not central to the documented consumer experience |
| Forms | Its clearest documented strength: conditional questions, prefill, progress-saving, co-borrower handling |
| Filtering | Not applicable to the consumer flow |
| Document viewing | Document upload and e-signature are part of the flow but not specifically documented as a distinguishing UX strength |
| Multi-panel layouts | Not applicable to its largely single-flow, mobile-oriented consumer design |
| Performance philosophy | Reviewed positively for reducing borrower drop-off and loan-officer support-call volume — evidence that good UX has a measurable operational payoff |
| Accessibility | Not deeply documented in available reviews |
| AI integration | Increasingly present in newer offerings but not the basis of its original UX reputation |

**Strengths**: progressive disclosure done well (only ask what's relevant to the current state); measurable business impact from UX investment (reduced drop-off and support burden); an integrated application-to-close flow avoiding platform switching.
**Weaknesses / limitation of the comparison itself**: the well-reviewed part of Blend is a one-time consumer wizard — structurally close to the opposite use case from MIL's all-day expert review tool. One reviewer specifically warned that Blend's back-office customization options can create "training delays and confusion with a large user base" — the more relevant, cautionary data point for MIL.
**What MIL should adopt**: progressive disclosure (show only relevant fields/actions for the current state, already reflected in Workspace FR-076); the general evidence that UX investment measurably reduces operational cost, useful for MIL's own future ROI case.
**What MIL should avoid**: assuming a consumer-wizard flow's praise transfers to an internal expert tool; over-customization that creates the "confusion at scale" its own reviewers flagged.
**Trade-offs**: Blend is the weakest direct analogue in this document for MIL's actual persona (the underwriter) — its most public praise concerns a different user (the borrower) performing a different kind of task (a one-time application, not a daily expert review).

---

### Temenos

| Dimension | Finding (Tier 2 — aggregated review evidence) |
|---|---|
| Primary users | Bank back-office staff and product/operations teams configuring core banking functions (broader than MIL's mortgage-specific scope) |
| Main workflow | Configure and operate core banking products, accounts, and transactions across a large, modular platform |
| Navigation | Reviewers describe well-sequenced tabs positively, but also describe the platform as "too granular," making it hard to determine "what does what" |
| Information hierarchy | Not strongly documented either way |
| Search | Not a specifically praised or criticized area in available commentary |
| Data density | High, reflecting the breadth of core-banking functionality exposed |
| Keyboard workflow | Not documented as a focus area |
| Tables | Not a specific point of praise or criticism |
| Forms | Configuration-heavy; described as requiring significant time to customize and optimize |
| Filtering | Not specifically documented |
| Document viewing | Not central to its documented core-banking focus |
| Multi-panel layouts | Not documented |
| Performance philosophy | No specific praise/complaint pattern found in available sources |
| Accessibility | Not documented in available reviews |
| AI integration | Not a defining part of its documented UX reputation as of this research |

**Strengths**: reliability, scalability, integration breadth; generally higher aggregated satisfaction than some peers in the same category.
**Weaknesses**: granularity without conceptual clarity ("too granular... difficult to find out what does what"); lengthy setup/customization time; reviewers note even a skilled specialist needs significant time to fully master the system.
**What MIL should adopt**: no specific pattern stands out strongly enough in available evidence to recommend direct adoption; the clearest lesson here is cautionary.
**What MIL should avoid**: granularity that outpaces conceptual clarity — exposing many controls is not the same as making a system easy to build a correct mental model of. This directly reinforces MIL's existing progressive-disclosure and cognitive-load rules (Design System FR-076).
**Trade-offs / limitation**: Temenos's actual domain (core banking) is broader and more transactionally complex than MIL's mortgage-intelligence scope; some of its documented complexity may be inherent to that domain breadth rather than a pure UX failing, and this finding should be read with that caveat.

---

### Finastra

| Dimension | Finding (Tier 2 — thinnest available evidence in this research set) |
|---|---|
| Primary users | Bank and lender back-office staff across a broad suite of banking and lending products |
| Main workflow, navigation, information hierarchy, search, density, keyboard workflow, tables, forms, filtering, document viewing, multi-panel layouts, performance, accessibility, AI integration | Available aggregated review volume for Finastra is markedly lower than for Temenos in the sources consulted for this research, and no dimension-specific UX finding strong enough to state with confidence was identified. Rather than infer or invent detail to fill these fields, this dossier states plainly that reliable, specific findings were not available. |

**Strengths**: broad functional and integration coverage across banking and lending products; an established position among large financial institutions.
**Weaknesses**: comparatively lower aggregated satisfaction scores than Temenos in the review platforms consulted; no distinguishing, well-documented UX strength was found in available research.
**What MIL should adopt**: no specific pattern strongly recommended by available evidence.
**What MIL should avoid**: treating broad functional coverage as a substitute for a coherent information architecture — the same lesson as Temenos, independently reinforced rather than contradicted by this second data point.
**Trade-offs / limitation**: this is the entry with the thinnest available public evidence in this entire document; conclusions here are the lowest-confidence in this research set, and this is stated plainly rather than compensated for with invented detail, per this document's explicit methodology (FR-005).

---

## Group C: General Enterprise UX (Tier 2 — Reasoned from Aggregated Evidence)

### Atlassian (Jira / Confluence)

| Dimension | Finding (Tier 2 — aggregated review evidence and industry commentary) |
|---|---|
| Primary users | Software/IT teams (Jira: issue tracking; Confluence: documentation) |
| Main workflow | Track work items through configurable workflows; document and link work to pages |
| Navigation | Multi-level, highly configurable; flexibility historically at some cost to first-time discoverability |
| Information hierarchy | Configurable to the point that consistency across different teams' own instances is famously variable |
| Search | Present but historically not as fast or as central to product identity as Linear's |
| Data density | Moderate, heavily influenced by admin-level configuration choices that vary instance to instance |
| Keyboard workflow | Present but not central to its identity the way it is for Linear/VS Code |
| Tables | Configurable boards/backlogs; flexibility frequently cited as a source of "every team's instance looks and works differently" complaints |
| Forms | Issue-creation forms can become very long and field-heavy as an organization adds custom fields over time — a well-known complexity-creep problem |
| Filtering | A powerful structured query language (JQL) for power users, with a steep learning curve for casual users |
| Document viewing | Confluence's page rendering is solid but not a distinguishing strength relative to Notion's more modern editor |
| Multi-panel layouts | Present (issue detail panels) but less disciplined/restrained than Linear's |
| Performance philosophy | Frequently cited in industry commentary as feeling slower than newer competitors — Linear has explicitly positioned itself against this reputation |
| Accessibility | Reasonably mature given its long enterprise/government customer base and associated compliance obligations |
| AI integration | "Atlassian Intelligence" added contextually across products, following the same assistive-not-chat-first trend seen elsewhere in this research |

**Strengths**: JQL as a powerful structured-query precedent; deep configurability for genuinely diverse team workflows; mature accessibility given a long enterprise/compliance history.
**Weaknesses**: configurability without enough default discipline leads to inconsistent, organization-specific experiences and organically-grown, field-heavy forms; widely reputed (including via competitors' own positioning) as slower/heavier than newer alternatives.
**What MIL should adopt**: a structured, powerful query/filter language exposed through an approachable surface — JQL's core idea, tempered by Linear's friendlier saved-views model (Workspace FR-020, FR-068).
**What MIL should avoid**: unconstrained per-instance/per-team configurability that erodes "one meaning, one representation" — precisely why MIL's closed design system exists (Design System FR-078–082).
**Trade-offs**: Atlassian's flexibility serves an enormous diversity of unrelated teams and workflows; MIL serves one well-defined workflow and should trade that flexibility for the consistency it costs Atlassian.

---

### Salesforce

| Dimension | Finding (Tier 2 — aggregated review evidence and industry commentary) |
|---|---|
| Primary users | Sales, service, and marketing teams; extremely broad, heavily customized per organization |
| Main workflow | Manage records (leads, accounts, cases) through configurable objects, views, and automations |
| Navigation | Deep and multi-level; widely echoed user commentary describes it as visually and structurally dated ("looks like the 90s") despite ongoing redesign efforts |
| Information hierarchy | Highly configurable per organization; consistency depends entirely on each customer's own admin discipline, not on the product enforcing one |
| Search | Global search present; quality/speed perception varies by org configuration and data volume |
| Data density | Widely variable by configuration; often criticized as cluttered ("interface is cluttered with features, buttons, and fields") |
| Keyboard workflow | Not a strength or focus area in its public reputation |
| Tables | Powerful, configurable list views, but inconsistent across the many modules (Sales Cloud, Service Cloud, etc.) a single organization may use |
| Forms | Extremely configurable — simultaneously its greatest customer-facing strength and its most cited UX weakness (inconsistency, clutter) |
| Filtering | Powerful (list-view filters, reports) but with a learning curve tied to overall platform complexity |
| Document viewing | Not a core strength; file handling is a bolted-on capability relative to its record-centric core |
| Multi-panel layouts | Present but inconsistent across modules; switching between clouds "requires learning slightly different interfaces and workflows" per aggregated commentary |
| Performance philosophy | Perception highly dependent on org-specific customization load; not a consistently fast experience across all customers |
| Accessibility | A long-standing, mature accessibility program exists given regulatory obligations of Salesforce's own large customers, though base product density/complexity can still create practical usability barriers regardless of technical conformance |
| AI integration | Heavy investment in embedded, contextual AI (Einstein, Agentforce) anchored to the record being viewed, rather than a separate destination |

**Strengths**: enormous configurability and functional breadth serving very diverse business needs; embedded, record-anchored (not separate-destination) AI placement.
**Weaknesses**: widely and consistently described, independently across many reviewers, as visually dated and inconsistent across its own modules — complexity/clutter is one of the most consistently repeated criticisms of any product in this research set.
**What MIL should adopt**: contextual, record-anchored AI placement — reinforcing, again, MIL's own application-anchored Copilot decision.
**What MIL should avoid**: allowing per-deployment/per-module configurability to fragment visual and interaction consistency. This is the single most repeated failure mode across the entire "general enterprise UX" category researched here (Atlassian, Salesforce, and ServiceNow each show a version of it), and is the strongest independent justification available for MIL's closed, non-per-tenant-customizable design system.
**Trade-offs**: Salesforce optimizes for near-infinite per-customer configurability across unrelated industries; MIL's single-domain, single-institution-type focus means it does not need, and should explicitly refuse, that same degree of structural flexibility.

---

### ServiceNow

| Dimension | Finding (Tier 2 — aggregated review evidence) |
|---|---|
| Primary users | IT service management teams and, increasingly, broader enterprise workflow teams |
| Main workflow | Route and resolve tickets/requests through configurable workflow states |
| Navigation | Described in aggregated reviews as "clunky and hard to navigate," with users specifically citing difficulty finding things |
| Information hierarchy | Not a documented strength; reviewers cite a UI that "hasn't really changed much" and needs modernization |
| Search | Present but not a specifically praised differentiator |
| Data density | Variable by configuration; custom dashboards specifically flagged as a common source of poor performance when built inefficiently |
| Keyboard workflow | Not a documented focus area |
| Tables | Configurable list views; not specifically praised |
| Forms | Highly configurable (a core value proposition for IT admins) but showing the same double-edged pattern as Salesforce/Atlassian — configurability without enforced consistency |
| Filtering | Present and functional, not a distinguishing strength |
| Document viewing | Not central to its ticket/workflow-centric design |
| Multi-panel layouts | Not a documented strength |
| Performance philosophy | A specifically and repeatedly cited weakness — both platform navigation speed and custom-dashboard performance are named complaints |
| Accessibility | Enterprise/government customer base implies compliance-driven investment, but this coexists with the base navigation complaints noted above — technical conformance and practical usability are not the same thing |
| AI integration | Heavy recent investment in "Now Assist" AI embedded contextually into workflows, again following the anchored-not-separate pattern seen across this research |

**Strengths**: deep workflow-configuration power for IT/enterprise operations; growing contextual AI investment.
**Weaknesses**: the most consistently criticized navigation and performance experience of any product in this entire research set — "clunky," "hard to navigate," "hasn't really changed much," with specific, repeated complaints about finding things and dashboard slowness.
**What MIL should adopt**: little from ServiceNow's own execution; its primary value here is as the clearest cautionary example in this research of what happens when configurability and legacy accumulation are allowed to outpace navigational clarity and performance discipline over a long product lifespan.
**What MIL should avoid**: allowing incremental feature/configuration accumulation — which MIL will face too, over years of operation — to erode navigational clarity. This is precisely why MIL's Design System's closed-token, closed-icon, one-pattern-per-concept rules exist: to resist exactly this kind of slow drift.
**Trade-offs**: none to recommend adopting; ServiceNow's evidentiary value in this document is as a warning, not a model.

---

# Part II — Cross-Product Comparisons

**How do Stripe and Linear differ?** Both are restrained and fast, but they optimize for different risk profiles. Stripe is conservative about write-confirmation because its data is money — optimistic UI is reserved for low-risk settings, never for a charge or payout. Linear is aggressively optimistic everywhere because its data (issue status) is cheap to be wrong about and trivial to correct. MIL's data spans both categories within a single product — application metadata and UI preferences are Linear-like (safe to be optimistic about), but verifications and overrides are Stripe-like (money- and record-adjacent, requiring confirmed writes). MIL must therefore consciously apply Stripe's caution to audit-critical actions and Linear's speed to everything else, rather than picking one philosophy uniformly (this is already the Design System's stated optimistic-UI policy; this comparison is the evidentiary justification for it).

**Why is Bloomberg optimized for experts?** Not because its designers chose density for its own sake, but because its users are pre-trained (often through a formal, paid course) before they ever touch the product, and they use it for years, all day. Bloomberg's own design team has publicly framed their job as concealing — not eliminating — decades of accumulated complexity behind memorized short commands. This is an optimization that only pays off when the up-front training cost is amortized over a very long, very frequent usage period by a stable, expert user base. MIL's underwriters share the "long, frequent usage" property but explicitly do not share the "formally pre-trained before first use" property (Workspace SC-006 requires productivity within 15 minutes, unaided) — so Bloomberg's density is a valid inspiration, but its *mechanism* (memorized commands) is not.

**Why is GitHub easy to scan?** Because it has one clear visual subject per screen (the diff, the issue, the file) and treats everything else — comments, metadata, history — as secondary and spatially anchored to the specific part of the subject it relates to. Scannability comes from *subordination*, not from minimalism for its own sake: GitHub is not sparse, but a viewer always knows what the primary thing on screen is. This is directly the model for MIL's own Application Workspace: the finding or evidence in question should always be the unambiguous visual subject, with citations, history, and metadata clearly subordinate and spatially anchored to it.

**Why does VS Code scale so well?** Because it separates "what's visible by default" from "what's available," and makes the entire available set reachable through one consistent mechanism (the command palette) rather than requiring the visible chrome to grow with the feature set. A code editor with a hundred thousand possible commands does not need a hundred thousand visible buttons — it needs one excellent way to find any of them on demand. This is precisely the principle behind MIL's own command-palette-first navigation (Workspace FR-002): the visible interface should not need to grow as MIL's own feature set grows over the product's lifetime.

**Why does Figma's panel system work?** Because the panels are *selection-scoped*, not static. The properties panel does not show every possible property Figma supports — it shows only the properties relevant to whatever is currently selected. This is the opposite failure mode from Salesforce/ServiceNow's problem (showing everything, all the time, regardless of relevance). MIL's Evidence Explorer and relationship view should follow the same discipline: show only what's relevant to the currently selected evidence item or finding, not a permanently-visible, ever-growing panel of every possible piece of context.

**Why do enterprise CRMs often feel slow?** Based on the aggregated evidence in this research (Salesforce, ServiceNow, and to a lesser extent Atlassian), the recurring pattern is not raw technical latency alone — it is **configurability without a forcing function toward consistency**. When any customer, admin, or team can add fields, panels, and modules independently over many years, the product accumulates inconsistent, redundant, and rarely-cleaned-up surface area, and *that* accumulated inconsistency is what users experience as "slow" and "clunky," even when a specific screen's raw load time is acceptable. Perceived speed is as much an information-architecture property as a technical one. This is the strongest possible independent argument for MIL's own closed, non-per-tenant-customizable design system (Design System FR-078–082): the goal is not just faster code, but preventing the slow accumulation of inconsistency that causes users to *perceive* even a technically fast product as slow.

**Bloomberg vs. VS Code — two paths to expert density, only one of which MIL can copy.** Both serve expert, all-day, keyboard-heavy users at high information density. Bloomberg achieves this through memorized, opaque commands acquired via formal training; VS Code achieves the same density and speed through a *discoverable* command palette that requires no training at all — a user can find any command by typing what they're thinking, not what they memorized. MIL must follow VS Code's mechanism to reach Bloomberg's density, precisely because of Workspace SC-006's no-training requirement.

**Linear vs. Notion — two different definitions of "fast."** Linear is fast because it is maximally optimistic and minimally flexible (a narrow, well-defined data model it can move quickly because it doesn't have to). Notion is flexible-but-comparatively-slower because its content model must accommodate near-arbitrary structure. MIL's application/evidence/finding data model is well-defined and narrow, much closer to Linear's than to Notion's — meaning MIL is structurally positioned to achieve Linear-like speed and should not import Notion's performance trade-offs by making its own data model more flexible than it needs to be.

---

# Part III — MIL UX Principles

These are MIL's product laws. Each includes its rationale, tracing to specific research findings above, and, where relevant, its precedence relative to other principles.

1. **Evidence First.** Every AI-generated claim shown to a user must be one action from its supporting evidence and source document. *Rationale*: this is the platform's foundational constitutional commitment (Principles II, III), and GitHub's line-anchored comment pattern is the clearest existing proof that this is achievable without sacrificing usability. **Precedence: highest.** No other principle in this list may be satisfied at Evidence First's expense.

2. **Human in Control.** The interface must always make clear what a human has verified versus what remains an unconfirmed AI output, and must never allow a workflow-advancing action to be taken by anything other than an explicit, attributed human act. *Rationale*: directly implements Constitution Principle I; reinforced by the research finding that no product studied here allows an AI feature to take an unreviewed, consequential action on the user's behalf — every AI integration found in this research (GitHub, VS Code, Notion, Salesforce, ServiceNow) is assistive and dismissible, never autonomous. **Precedence: equal-highest, alongside Evidence First.**

3. **Minimal Cognitive Load.** Every screen must minimize the number of things a user must hold in their head at once. *Rationale*: directly informed by the Temenos and Salesforce findings that granularity/configurability without a corresponding discipline in what's shown at once ("too granular... difficult to find out what does what") is a well-documented, independent-across-multiple-products failure mode, not a one-off complaint.

4. **Keyboard First.** Every primary workflow must be fully operable by keyboard alone, with a command palette as the universal fallback for anything not bound to a dedicated shortcut. *Rationale*: directly modeled on VS Code and Linear's demonstrated approach, adjusted per the Bloomberg finding to require *discoverable* shortcuts (command palette, "?" help overlay), never memorized-only ones. **Precedence: subordinate to Evidence First and Human in Control** — a keyboard shortcut must never make it easier to skip viewing evidence or to bypass an attribution requirement.

5. **Progressive Disclosure.** Advanced or infrequently needed detail is available on demand, never shown by default. *Rationale*: the clearest positive lesson from Blend's consumer-flow praise (show only what's relevant to the current state) and the clearest negative lesson from Temenos/Salesforce (show everything, regardless of relevance, and users lose the ability to build a correct mental model).

6. **Performance is a Feature.** No visual or interaction choice may come at a measurable cost to responsiveness at MIL's stated scale (100,000+ applications). *Rationale*: VS Code's and Stripe's virtualization/lazy-loading discipline versus Notion's and ServiceNow's documented performance complaints at scale are the clearest positive/negative pairing in this research. **Precedence: subordinate to Evidence First and Human in Control** — MIL will not sacrifice audit-critical write-confirmation (a Human in Control requirement) for the sake of perceived speed, per the Design System's existing selective-optimistic-UI policy.

7. **One Meaning, One Representation.** A given concept is represented exactly one way, everywhere it appears, for the lifetime of the product. *Rationale*: the single most repeated *negative* finding across the entire "general enterprise UX" category researched here (Atlassian, Salesforce, ServiceNow all show a version of "the same concept looks different in different modules/instances") — this principle exists specifically because three independent products in this research fail at it.

8. **Context Before Conversation.** Any AI interaction is anchored to, and subordinate to, the specific record it concerns — never offered as a general-purpose, context-free chat destination. *Rationale*: every AI integration studied in this research (GitHub Copilot, VS Code Copilot, Notion AI, Salesforce Einstein/Agentforce, ServiceNow Now Assist) is contextual and anchored to a specific record or selection, not a separate, general-purpose chat surface — this is not one product's idiosyncratic choice but a converging pattern across every AI-integrated product studied.

9. **Discoverable Density, Not Memorized Density.** MIL may be as information-dense as an expert tool requires, but every control that density depends on must be discoverable (via visible affordance, command palette, or in-product help) rather than requiring memorization or external training. *Rationale*: this is the direct, necessary correction to naively adopting Bloomberg Terminal's density — Bloomberg's own design team publicly frames their work as concealing complexity behind a system that still requires months to learn; MIL's own success criteria (Workspace SC-006) make that specific trade-off unavailable.

**Resolving conflicts between these principles**: where a design choice would satisfy one principle only at the expense of Evidence First or Human in Control, Evidence First and Human in Control win, without exception. Among the remaining principles, Minimal Cognitive Load and Progressive Disclosure take precedence over Keyboard First and Performance is a Feature wherever they conflict (a faster or more shortcut-rich interaction that increases what a user must hold in their head is not an acceptable trade).

---

# Part IV — MIL Interaction Principles

**Navigation**: Flat, command-palette-first (per VS Code); no deep hierarchical menus (rejecting Notion's nested-page model and Salesforce/ServiceNow's multi-level, module-inconsistent navigation). Every primary destination reachable within two interactions, per Workspace FR-008.

**Searching**: Human-identifier-first (borrower name, loan number, LOS reference), never UUID-first (see Anti-Patterns) — directly informed by Encompass's documented search/state-loss failure and Stripe's model of surfacing human-meaningful identifiers as primary while keeping technical IDs available but secondary.

**Reviewing evidence**: Selection-scoped, always-relevant side panels (per Figma), never an ever-growing, always-visible panel of every possible piece of context (rejecting the Salesforce/ServiceNow "show everything at once" pattern).

**Reviewing documents**: Line/region-anchored highlighting directly modeled on GitHub's diff-comment pattern, adapted for multi-page PDFs; pinned-vs-preview tab discipline per VS Code when multiple documents are open.

**Copilot interaction**: Always anchored to one record (Context Before Conversation); contextual invocation, not a persistent separate destination (per GitHub Copilot, VS Code Copilot, Notion AI, and every other AI integration studied); citations resolve in one action, matching GitHub's evidence-linking maturity.

**Tables**: Virtualized, windowed rendering as a default assumption, not a later optimization (per VS Code and Stripe); monospaced numeric/tabular alignment (per Bloomberg and Stripe); multiple saved views over one dataset (per Notion and Linear).

**Filtering**: Structured, composable filter criteria (per Stripe's filter builder and Atlassian's JQL), saved as named views (per Linear), never requiring the user to reconstruct criteria from scratch or lose state by navigating away (rejecting Encompass's documented failure mode).

**Loading**: Distinct, immediate (sub-100ms) loading-state feedback for every data-fetching action, skeleton loading where content shape is known in advance (per VS Code and Stripe's perceived-instantness engineering); never a frozen or ambiguous screen (rejecting the ServiceNow and Notion documented performance-perception complaints).

**Error handling**: Plain-language, specific, retry-capable error states, at the granularity of the actual failure (a single failed document does not fail the whole application view) — directly informed by Encompass's crash/data-loss complaints as the negative exemplar to avoid.

**Notifications**: Grouped, actionable, individually dismissible; never an undifferentiated flood — informed by the general enterprise-software pattern (Salesforce, ServiceNow) of alert/notification fatigue in heavily-configured systems.

**Focus management**: A single, consistent, always-visible focus indicator; a fully specified keyboard-navigation and focus-trap model for every overlay (dialog, drawer, panel) — directly modeled on VS Code and GitHub's mature accessibility practice, in explicit contrast to Bloomberg's and the Tier 2 mortgage/CRM products' comparatively undocumented accessibility posture.

---

# Part V — MIL Anti-Patterns

Each entry names the pattern, why it is rejected, a real exemplar from this research where one exists, and what MIL does instead.

1. **Infinite scrolling everywhere.** *Why rejected*: loses scan-ability, back-button integrity, and a stable sense of how much data remains — unacceptable for triaging tens of thousands of records under time pressure. *Exemplar*: Notion's block-based lazy-loading is a legitimate, narrow use of progressive loading for content blocks, but generalizing it to record-list triage (a queue) would be a category error. *MIL does instead*: virtualized, paginated tables with a persistent total count (Workspace FR-017, FR-024).

2. **ChatGPT-style full-screen chat.** *Why rejected*: encourages ambiguous scope and is the single biggest risk to AI context isolation (Constitution Principle V). *Exemplar*: no AI-integrated product researched here (GitHub, VS Code, Notion, Salesforce, ServiceNow) adopts this pattern for its primary AI surface — this is a converging, cross-product finding, not a single product's idiosyncratic choice. *MIL does instead*: an application-anchored Copilot panel (Workspace FR-062).

3. **Hidden navigation.** *Why rejected*: forces users to memorize paths to functionality rather than discovering them, directly conflicting with Discoverable Density. *Exemplar*: contrasts with VS Code's and Linear's command-palette-as-universal-fallback approach, which keeps every function findable without being permanently visible. *MIL does instead*: a command palette reachable by one shortcut from anywhere (Workspace FR-002).

4. **Consumer-style animations.** *Why rejected*: bouncy, elaborate, multi-stage motion is a cost, not a delight, at hundreds of repetitions per day, and conflicts with reduced-motion accessibility requirements. *Exemplar*: Linear's motion discipline (short, purposeful, state-change-only) versus generic consumer-app motion. *MIL does instead*: purposeful, short-duration motion only (Design System FR-038–041).

5. **Dashboard overload.** *Why rejected*: a dashboard trying to serve every persona's every need becomes legible to none of them. *Exemplar*: the Salesforce/ServiceNow pattern of ever-growing, per-org-configured surface area that erodes clarity over time. *MIL does instead*: a Dashboard scoped tightly to one user's own work (Workspace FR-028), with org-wide analytics explicitly deferred to a separate future workspace.

6. **Rainbow status colors.** *Why rejected*: collapsing distinct meanings (workflow status, AI confidence, business risk) into one undifferentiated color language creates exactly the ambiguity Constitution Principle III forbids. *Exemplar*: no product researched here was found to conflate these meanings this way; this anti-pattern is a preemptive, principle-driven rejection rather than one drawn from a specific bad exemplar. *MIL does instead*: three structurally distinct color families — Status, Evidence/Confidence, AI (Design System FR-022–024).

7. **Modal abuse.** *Why rejected*: interrupts flow and hides the surrounding evidence context a reviewer is actively reasoning about. *Exemplar*: contrasts with Stripe's and Figma's preference for contextual side panels over full-screen modals for routine tasks. *MIL does instead*: dialogs reserved strictly for blocking, irreversible confirmations; drawers/panels for everything else (Design System FR-050–051).

8. **UUID-first workflows.** *Why rejected*: forces users to work with meaningless technical identifiers instead of the human-meaningful identifiers they actually have on hand; a named, mandatory constraint on this platform. *Exemplar*: Encompass's documented search/state-loss complaints are a partial cautionary tale for search generally, though not UUID-specific; this anti-pattern is otherwise a direct, non-negotiable platform requirement rather than one drawn from a specific researched failure. *MIL does instead*: search and display exclusively by borrower name, loan number, and LOS reference (Workspace FR-006, FR-009–010).

9. **Decorative AI.** *Why rejected*: AI features added for their own sake, without evidentiary grounding or a clear task purpose, erode trust in the specific, load-bearing AI features that do matter. *Exemplar*: contrasts with the restrained, task-specific AI placement found in GitHub Copilot, VS Code Copilot, and Notion AI, none of which add AI as a decorative or default-visible surface. *MIL does instead*: every Copilot response is either cited or explicitly states insufficient grounding — never a decorative or unsupported presence (Workspace FR-057).

10. **Generic admin-template layouts.** *Why rejected*: reads as an assembled, uncustomized product — precisely the "student project" impression this platform is explicitly designed to avoid. *Exemplar*: contrasts with the deliberate, disciplined visual restraint of Stripe, Linear, and GitHub, none of which resemble an off-the-shelf admin template. *MIL does instead*: a closed, purpose-built design system (Design System specification, in its entirety).

11. **Per-tenant/per-team visual configurability.** *Why rejected*: this is the single most repeated failure mode independently found across three unrelated products in this research (Atlassian, Salesforce, ServiceNow) — configurability that is not paired with a forcing function toward consistency degrades into exactly the "clunky," "looks like the 90s," "every instance is different" reputation all three carry. *Exemplar*: Salesforce ("switching between Sales Cloud and Service Cloud requires learning slightly different interfaces"), Atlassian ("every team's Jira looks and works differently"), ServiceNow ("hasn't really changed much... difficult to find things"). *MIL does instead*: a single, closed design system with no per-institution visual customization (Design System FR-078–082).

12. **Memorized-command-only interaction as a substitute for discoverable UI.** *Why rejected*: this pattern works for Bloomberg specifically because its users receive formal, often paid, multi-month training before first use — a precondition MIL's own success criteria explicitly rule out. *Exemplar*: Bloomberg Terminal, whose own design team publicly describes their work as concealing, not eliminating, this complexity. *MIL does instead*: MIL UX Principle 9, Discoverable Density, Not Memorized Density.

---

# Part VI — MIL Design Decisions

**Decision: The Copilot is anchored to a single application; there is no global, cross-application chat destination.**
*Reason*: every AI integration researched here (GitHub, VS Code, Notion, Salesforce, ServiceNow) places AI contextually, never as a general-purpose destination, and Constitution Principle V requires strict AI context isolation between applications.
*Alternative considered*: a persistent, global Copilot panel available from anywhere in the product (a "ChatGPT sidebar" pattern), which would allow a user to ask cross-application questions (e.g., portfolio-wide patterns) without navigating to a specific record first.
*Why rejected*: no researched product's primary, most-trusted AI feature works this way; a global panel makes it structurally easy to blur which application's evidence is actually grounding a given answer, directly risking Constitution Principle V and undermining Evidence First.
*Long-term implications*: cross-application or portfolio-wide AI analysis (e.g., "how does this application's DTI compare to typical approved applications") remains a genuinely valuable, real future capability — but it must be built as an explicitly separate, clearly-labeled feature with its own grounding model, not smuggled in as a side effect of a more "modern-feeling" global chat surface (see Workspace specification, Future Expansion).

**Decision: MIL adopts Bloomberg-level information density but explicitly rejects Bloomberg's memorized-command interaction mechanism.**
*Reason*: Bloomberg is the strongest available evidence that expert users value and can operate at extreme density under time pressure — but its own design team's public description of their work (concealing complexity behind decades of accumulated, memorized commands) reveals that the mechanism enabling that density is a multi-month training investment, not the density itself.
*Alternative considered*: adopting Bloomberg's UI more literally — a terse, command-driven interaction layer for expert underwriters who use the product daily, on the theory that daily expert users would tolerate and even prefer it, the same way Bloomberg's traders do.
*Why rejected*: MIL's own Workspace specification already commits to a new underwriter being productive within 15 minutes with no external training (Workspace SC-006) — a requirement Bloomberg's own documented onboarding timeline (3–6 months) makes structurally incompatible with a literal Bloomberg-style command layer.
*Long-term implications*: MIL must invest in making its command palette genuinely discoverable (fuzzy search, suggestions, visible affordances) rather than treating "our users are experts, they'll learn it" as a substitute for that investment — discoverability is the harder, more valuable engineering problem, not a compromise.

**Decision: Evidence, Confidence, and Risk each get a structurally distinct color family; none reuse the others' hues or visual grammar.**
*Reason*: a rushed reviewer must be able to tell, in a single glance, whether a color means "the AI is uncertain," "there is a compliance/business risk," or "the workflow is behind schedule" — three genuinely different facts a reviewer must not confuse.
*Alternative considered*: a single, universal red/amber/green semantic scheme applied consistently across all three meanings, for simplicity and because this is the most common pattern across generic enterprise software.
*Why rejected*: this is precisely the kind of collapsed, ambiguous signaling Constitution Principle III (Explainability) exists to prevent; no researched product that handles genuinely distinct risk categories (this research did not find a strong positive exemplar for this specific problem, which is itself notable — most researched products have only one axis of "status" to communicate, not three simultaneously, which is part of why this is a MIL-specific, not borrowed, design decision).
*Long-term implications*: every future chart, badge, or indicator introduced to the product must be checked against which of the three families it belongs to before a color is chosen — this is a permanent constraint on the design system's evolution, not a one-time decision (see Design System, Future Extensibility).

**Decision: MIL's information architecture is flat and command-palette-first; it will not adopt deep, nested hierarchical navigation even as the product's feature set grows.**
*Reason*: VS Code and Linear both demonstrate that a flat, palette-driven model scales from a small feature set to a very large one without requiring the visible navigation chrome to grow; Notion's nested-page model works only because its use case (open-ended content organization) benefits from user-defined hierarchy in a way MIL's fixed, well-understood workflow does not need.
*Alternative considered*: a traditional, growing sidebar tree (as Salesforce, Atlassian, and ServiceNow all use to varying degrees), which is a common, familiar enterprise pattern and would be a "safe," conventional choice.
*Why rejected*: this is the single most repeated negative finding in the entire "general enterprise UX" category researched — configurability and growth of a hierarchical nav structure over time is directly implicated in the "clunky," "hard to find things," "looks dated" reputation shared by Salesforce, ServiceNow, and (to a lesser degree) Atlassian.
*Long-term implications*: every future MIL feature must be reachable via the command palette from day one of its existence, not added to a growing sidebar as an afterthought — this is an ongoing engineering discipline, not a one-time architectural choice, and it is the main safeguard against MIL slowly accumulating ServiceNow's reputation over its own multi-year lifespan.

**Decision: MIL's document/table-based (not canvas-based) architecture is treated as a deliberate accessibility advantage, not a limitation to work around.**
*Reason*: Figma's well-documented, industry-wide challenge making a freeform canvas fully screen-reader accessible does not apply to MIL, precisely because MIL's core content (documents, evidence, tables, findings) is structured, not freeform.
*Alternative considered*: none seriously — this decision is included specifically to record, for future contributors, that MIL's structural choice should not be second-guessed toward a more "visual" or canvas-like paradigm (e.g., a freeform relationship-mapping canvas for the Knowledge Graph) without recognizing the accessibility cost such a change would reintroduce.
*Why rejected (i.e., why the canvas-like alternative is preemptively discouraged)*: the Knowledge Graph requirement in the Workspace specification (FR-064–067) already anticipates this tension by requiring a filtered/list-based fallback wherever a graph view would become illegible or inaccessible — this decision simply records the research basis for that requirement.
*Long-term implications*: any future feature proposal resembling a freeform visual canvas should trigger an explicit accessibility review referencing this decision before proceeding.
