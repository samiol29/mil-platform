# Feature Specification: MIL Enterprise Design System

**Feature Branch**: `003-design-system`

**Created**: 2026-07-05

**Status**: Draft

**Input**: User description: "The Enterprise Design System for the Mortgage Intelligence & Verification Platform (MIL): the complete design language — philosophy, principles, typography, color, spacing, elevation, motion, states, domain-specific evidence/AI/confidence visual patterns, and accessibility rules — that every present and future frontend feature (beginning with the Underwriter Workspace) must follow for the lifetime of the product. Not an implementation: no frameworks, no CSS, no component code. A design constitution comparable in rigor and restraint to Stripe Dashboard, Linear, GitHub, Notion, VS Code, and Bloomberg Terminal, adapted for enterprise mortgage underwriting rather than copied from any one of them."

---

## Design Philosophy

A design system is not a style guide of pretty defaults; it is a **constraint mechanism**. Its purpose is to make the *correct* visual decision the *only convenient* one, so that a hundred different engineers building a hundred different screens over several years produce something that looks and behaves like it came from a single, disciplined hand.

For MIL specifically, the design system exists to serve three commitments that are not negotiable trade-offs against visual appeal — they *are* the visual appeal, by this product's standard:

1. **Cognitive load is the enemy.** Every underwriter using this product spends 6–10 hours a day inside it, reviewing dozens of data-dense records under time and accuracy pressure. A visual decision that is delightful on first impression but costs attention on the thousandth repetition is a defect, not a feature.
2. **Evidence is the source of truth, and the design must say so.** Every visual treatment involving an AI-generated claim, a confidence level, or a piece of evidence must make the distinction between "the system observed this" and "a human confirmed this" impossible to miss, even at a glance, even by someone in a hurry (Constitution Principles II, III).
3. **Restraint reads as competence.** In enterprise banking software, visual restraint — consistent density, a disciplined and small color vocabulary, quiet and purposeful motion — is what separates production software from a portfolio piece. A design that "shows off" is, in this domain, actively working against the product's credibility with the institutions (ICE, Blend, Wipro, Temenos, Finastra, and the banks and regulators behind them) that will judge it.

The design references studied for this system — Stripe Dashboard, Linear, GitHub, Notion, VS Code, Bloomberg Terminal, Figma — are studied for **principles**, not copied for **appearance**. What is extracted from each:

- **Stripe Dashboard**: restrained, trustworthy color use where every accent has earned meaning; typographic hierarchy that never relies on size alone.
- **Linear**: motion and interaction discipline — every animation communicates a state change and nothing is animated "because it looks nice"; extremely fast perceived performance.
- **GitHub**: mature patterns for evidence-linking (diffs, blame, citations, timelines) — the closest existing enterprise analogue to MIL's evidence-to-finding traceability.
- **Notion**: flexible content density without visual chaos — structure absorbs variety in content length and type without breaking layout.
- **VS Code**: a command-palette-first, keyboard-complete interaction model built for expert daily users, and a dual-theme (light/dark) discipline that treats dark mode as a first-class citizen, not an inverted afterthought.
- **Bloomberg Terminal**: the proof that extreme information density and speed can coexist with usability for expert users under time pressure — the reference point for what "enterprise-grade, not consumer-grade" actually looks like.
- **Figma**: precise, purposeful micro-interactions and a component/token architecture that scales across a very large surface area without fragmenting.

None of these products is a bank underwriting tool. MIL's design system adapts their discipline to a domain none of them serve: one where every color, icon, and state must also encode *evidentiary and regulatory meaning*, not just application state.

---

## Core Design Principles

1. **Clarity over decoration.** Nothing is added to a screen unless it reduces the time or effort required to reach a correct decision.
2. **One meaning, one representation.** A given concept (a confidence level, a status, a conflict) is represented exactly one way, everywhere it appears, for the lifetime of the product.
3. **Evidence is never visually equal to inference.** A verified fact, an AI-extracted fact, and an AI-generated finding are always visually distinguishable from one another, in every context they appear together.
4. **Density is a feature, not a compromise.** This system defaults toward showing more relevant information per screen than a typical consumer or marketing-oriented product would, because its users are experts operating at volume — but never at the cost of individual legibility or accessibility compliance.
5. **Motion explains, it does not entertain.** Every animation exists to communicate a state change, a spatial relationship, or a process in progress. An animation that cannot be justified this way does not belong in the system.
6. **Every interactive element has a fully defined state model.** Default, hover, focus, active/pressed, disabled, loading, and error states are specified for every component category before it exists, not improvised during implementation.
7. **Accessibility is baseline, not an enhancement.** WCAG 2.1 AA conformance, full keyboard operability, and reduced-motion support are properties every component must have from its first definition, not a pass applied afterward.
8. **The system is closed by default, extensible by process.** No engineer or designer introduces a new color, spacing value, type size, icon, or motion pattern outside this system without it being added to the system itself first — see Future Extensibility.

---

## Product Personality & Brand Identity

**Personality**: Precise. Calm under pressure. Quietly confident. Never cute, never alarmist, never chatty. MIL's tone is that of a trusted senior colleague who has already read every page of the file and tells you exactly what matters — not a mascot, not a hype-driven product, not a chatbot pretending to have a personality of its own.

**Brand identity within the product surface** (as distinct from external marketing brand, which is out of scope for this specification):

- The product's visual identity is carried almost entirely by its **type, color discipline, and spacing rhythm** — not by decorative brand marks, illustration, or a mascot. This is deliberate: in a tool used 6–10 hours a day, users stop seeing decorative branding within the first week, but they never stop being affected by inconsistent density or color noise.
- A single, small wordmark/logomark is used only in the persistent application chrome (e.g., top navigation) and in exported/printed evidentiary artifacts (for provenance and trust), never repeated decoratively within working screens.
- Brand color (a single, deliberately chosen accent — see Color Philosophy) is reserved for primary actions and focus/selection states. It is explicitly **not** used for status, risk, confidence, or AI signaling, which each have their own dedicated, non-overlapping color families (see Semantic Color Tokens, Status Colors, Evidence Colors, AI Colors) — conflating "our brand color" with "this thing is good/active/important" is a common weak default this system explicitly rejects (see Design Rationale).

---

## Consumers of This Specification (Personas)

### Frontend Engineer ("the primary consumer")

Builds every screen and component in every future frontend feature (starting with the Underwriter Workspace). Needs this specification to answer, without needing to ask a designer: *which token do I use, what state does this component need to support, and how do I know I got it right?*

### Product/UX Designer

Extends the system to new screens and flows. Needs this specification to define what is fixed (the system) versus what is theirs to compose (arrangements of the system's tokens and components) — and the process for proposing a genuine system change.

### Accessibility Auditor

Verifies conformance. Needs this specification to state testable, objective rules (contrast ratios, focus behavior, motion reduction, screen-reader behavior) rather than subjective visual judgment.

### Future Maintainer

Inherits this system years from now, likely without direct access to its original authors. Needs this specification to be self-explanatory: every rule states not just *what* but *why*, so a future change can be evaluated against the same reasoning that produced the original rule (mirroring the MIL engineering constitution's own governance model).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a New Screen Without Inventing New Values (Priority: P1)

A frontend engineer builds a screen that did not exist when this specification was written (e.g., a new report view). Using only this specification's typography, color, spacing, elevation, and component-state rules, they produce a screen that is visually indistinguishable in quality and consistency from screens built by a different engineer, without needing to invent a single new visual value or ask a designer a clarifying question about basics (what color, what spacing, what type size).

**Why this priority**: This is the entire reason a design system exists. If this does not hold, the system has failed regardless of how well any individual section is written.

**Independent Test**: Give the specification alone (no screenshots, no existing screen to copy) to an engineer unfamiliar with the product and ask them to lay out a new data-heavy record view. Verify the resulting screen uses only defined type scale steps, spacing steps, and color tokens, and that a second engineer given the same brief produces a visually compatible (not necessarily identical, but compatible) result.

**Acceptance Scenarios**:

1. **Given** this specification and no other visual reference, **When** an engineer selects a text size, color, or spacing value for a new element, **Then** every value they select maps to a named token or scale step defined in this specification — no arbitrary or one-off value is introduced.
2. **Given** two engineers independently build the same category of screen (e.g., two different record-detail views) from this specification alone, **When** the results are compared, **Then** they use the same type scale, spacing rhythm, and color roles for equivalent elements, differing only in content, not in system.
3. **Given** a new interactive element is introduced, **When** it is built, **Then** its default, hover, focus, active, disabled, loading, and error states are all defined, none improvised.

---

### User Story 2 - Represent AI Confidence and Human Verification Without Ambiguity (Priority: P1)

A frontend engineer implements any surface showing an AI-extracted evidence value, an AI-generated finding, a confidence level, or a human verification/override — and, following this specification, produces a result in which a reviewer can instantly and correctly distinguish "the AI found this," "the AI is uncertain about this," and "a human confirmed or changed this," without reading any accompanying text.

**Why this priority**: This is the single most safety-critical visual requirement in the entire product, directly implementing Constitution Principles II, III, and I. A design system that gets typography wrong produces an ugly product; a design system that gets this wrong produces a *dangerous* one.

**Independent Test**: Present a reviewer (unfamiliar with the specific screen) with a mixed set of AI-extracted evidence, low-confidence findings, and human-overridden values, with all text labels hidden/obscured, and confirm they can still correctly categorize each item using visual treatment alone.

**Acceptance Scenarios**:

1. **Given** an AI-extracted evidence value and a human-verified value are shown together, **When** viewed without reading any label, **Then** they are visually distinguishable by more than color alone.
2. **Given** a finding with low extraction confidence, **When** displayed, **Then** its confidence treatment is visually distinct from a high-confidence finding, using a consistent scale applied identically everywhere confidence appears in the product.
3. **Given** an AI-generated finding that has since been overridden by a human, **When** displayed anywhere in the product (including historical/audit views), **Then** the override is visually evident and the original AI value remains visible, never silently replaced.

---

### User Story 3 - Verify Accessibility Conformance Objectively (Priority: P2)

An accessibility auditor evaluates any screen built under this system against explicit, numeric, testable rules — contrast ratios, focus indicator visibility, keyboard operability, motion-reduction behavior, and screen-reader announcement rules — and can produce a pass/fail result without subjective interpretation.

**Why this priority**: Accessibility conformance is a stated mandatory requirement of the broader product; a design system that only asserts "we care about accessibility" without testable rules cannot actually be audited or enforced.

**Independent Test**: Run an automated contrast/accessibility audit tool against a screen built under this system in both light and dark theme, and confirm zero violations against the rules stated in this specification.

**Acceptance Scenarios**:

1. **Given** any text and its background in either theme, **When** contrast is measured, **Then** it meets or exceeds the WCAG AA minimum defined in this specification for its text size and weight.
2. **Given** any interactive element, **When** it receives keyboard focus, **Then** a focus indicator meeting the contrast and visibility rules in this specification is shown, with no exceptions.
3. **Given** the operating system's reduced-motion preference is enabled, **When** any animated element in the system would normally animate, **Then** it instead presents its end state directly or via a minimal, non-parallax, non-bouncing transition, with no loss of the information the animation conveyed.

---

### User Story 4 - Extend the System Without Fragmenting It (Priority: P2)

A designer or engineer needs a pattern the system does not yet define (e.g., a new chart type, a new risk-indicator shape) and follows this specification's extensibility process to add it as a proper, named, versioned addition to the system — rather than inventing a one-off, undocumented visual treatment that only they know about.

**Why this priority**: Every design system that lacks a defined extension process degrades over time as ad hoc exceptions accumulate; this is how enterprise products visually decay into "student project" territory years after a strong initial launch.

**Independent Test**: Propose a plausible new pattern not covered by this specification (e.g., a new data-visualization chart type) and confirm the specification's Future Extensibility rules give an unambiguous answer for how it should be evaluated, named, and incorporated.

**Acceptance Scenarios**:

1. **Given** a genuinely new visual need not covered by this specification, **When** an engineer or designer wants to introduce it, **Then** this specification defines the criteria under which it must first be reviewed against existing tokens and patterns before any new value is introduced.
2. **Given** a new pattern is approved for addition, **When** it is added, **Then** it is named and structured consistently with this specification's existing naming conventions, not as an isolated exception.

---

### Edge Cases

- **A component needs a state this specification did not anticipate** (e.g., a "partially verified" state for a finding with multiple evidence items, some verified and some not): the system's state model must be extensible without requiring a wholesale redesign — see Component Design Principles.
- **Extremely long or short content in a fixed-layout element** (a one-character loan status vs. a multi-paragraph override reason): spacing and typography rules must hold across realistic content-length extremes, not only "ideal" placeholder content.
- **A screen must show both AI confidence and human risk assessment side by side**: the three color families (Status, Evidence/Confidence, AI) must remain visually distinguishable from one another even when displayed adjacently on the same screen — this is the hardest test of the color system's discipline and is treated as a first-class design requirement, not an edge case to patch later.
- **High-contrast OS mode conflicts with a themed surface color**: the system must define how its tokens resolve under a forced high-contrast mode without becoming illegible or losing state distinctions.
- **A user has both reduced motion and dark theme enabled simultaneously**: both preferences must be honored together without conflict; the system does not treat them as mutually exclusive configurations to test only in isolation.
- **A new locale requires longer translated strings than English originals**: type and spacing rules must not assume a fixed string length for any label, button, or status term (this specification does not define specific translations, but must not architecturally preclude them).
- **Print or export of an evidentiary artifact**: color, contrast, and iconography used to convey status/confidence/evidence meaning must survive a monochrome or low-color print/export context without losing meaning (a status conveyed only by a specific saturated color that disappears in grayscale printing is a failure of this system, not an acceptable limitation).

---

## Requirements *(mandatory)*

### Functional Requirements

#### A. Design Philosophy, Principles, Personality & Brand (Topics 1–4)

- **FR-001**: The system MUST define and publish a single, stable statement of design philosophy and core principles that every subsequent design decision can be evaluated against; this statement MUST NOT be re-litigated per feature.
- **FR-002**: The system MUST define a specific, named product personality (tone, restraint level, what the product is and is not) that governs copywriting tone, illustration use, and motion character consistently across the entire product.
- **FR-003**: Brand identity elements (wordmark, logomark, brand accent color) MUST be confined to persistent chrome and evidentiary export contexts; they MUST NOT be used decoratively within working screens, and the brand accent color MUST NOT double as a status, risk, confidence, or AI signal color.
- **FR-004**: Every principle in this system MUST state its rationale (why), not only its rule (what), so future maintainers can evaluate proposed exceptions against the original reasoning.

#### B. Typography System (Topics 5–8)

- **FR-005**: The system MUST define a single interface typeface family used for all UI text, distinct from any typeface used to render source document content (which must preserve the source document's own visual fidelity).
- **FR-006**: The system MUST define a constrained type scale of no more than 7–8 discrete size/weight/line-height combinations ("steps"), each with a defined semantic purpose (e.g., page title, section heading, body, caption, label, data/tabular value); no interface text may use a size outside this scale.
- **FR-007**: The system MUST designate one or more monospaced or tabular-figure typefaces reserved for numeric, financial, identifier, and code-like values, ensuring columns of numbers align visually wherever they appear in tables or summaries.
- **FR-008**: Where a secondary typeface is paired with the primary interface typeface (e.g., for emphasis or a distinct content category), the system MUST define the specific pairing and its restricted use — pairing MUST NOT be left to per-screen discretion.
- **FR-009**: The system MUST define a maximum comfortable line length (reading measure) for dense textual content (findings rationale, Copilot answers, override reasons) and require it be respected regardless of viewport width.
- **FR-010**: Every type scale step MUST specify its minimum contrast requirement against both the light and dark theme's defined surface tokens, satisfying WCAG AA at that step's typical size and weight.

#### C. Spatial Foundations: Spacing, Grid, Layout, Elevation, Radius, Shadow (Topics 9–14)

- **FR-011**: The system MUST define a single base spacing unit and a fixed, small multiple sequence derived from it; all padding, margin, and gap values in the product MUST be drawn from this sequence, with no arbitrary spacing values permitted.
- **FR-012**: The system MUST define a base layout grid (column structure and gutter rules) governing how content regions are arranged at each defined viewport breakpoint.
- **FR-013**: The system MUST define layout principles establishing which regions of the interface are fixed (persistent chrome, navigation) versus fluid (content areas), and how these regions relate to each other at every supported viewport size.
- **FR-014**: The system MUST define a small, fixed number of elevation levels (e.g., base surface, raised surface, overlay surface) each with a specific, consistent visual treatment; elevation MUST communicate a specific structural meaning (e.g., "this is temporarily on top of other content") and MUST NOT be used decoratively.
- **FR-015**: The system MUST define a small, fixed set of border-radius values, each mapped to a category of element (e.g., interactive controls vs. containers vs. data chips), applied consistently by category across the entire product.
- **FR-016**: The system MUST define shadow usage as minimal and strictly functional (indicating elevation/overlay state), rejecting decorative or heavy shadow treatments; every defined shadow value MUST correspond to exactly one elevation level.
- **FR-017**: The system MUST define minimum and default information density targets (e.g., typical row height in a data table, typical vertical rhythm in a form) appropriate to an expert, all-day, data-dense professional tool, distinct from consumer-app defaults.

#### D. Color System (Topics 15–23)

- **FR-018**: The system MUST define color as a two-tier architecture: primitive color values (raw color ramps, not directly meaningful) and semantic color tokens (named by role and meaning, e.g., "surface.background.primary," "text.critical," "border.focus"); all components and screens MUST reference semantic tokens only, never primitive values directly.
- **FR-019**: The system MUST define semantic surface tokens (background, raised-surface, overlay, disabled-surface, etc.) covering every surface context a component can appear on, for both light and dark theme.
- **FR-020**: The system MUST define semantic interaction tokens (default, hover, active/pressed, disabled) for every interactive element category, applied consistently regardless of the specific component using them.
- **FR-021**: The system MUST define a single, dedicated focus token (visual treatment for keyboard focus) used identically across every interactive element in the product, meeting the contrast and visibility rules required for accessibility conformance.
- **FR-022**: The system MUST define a small, fixed set of status colors (e.g., on-track, at-risk, overdue, blocked) used exclusively for application/workflow lifecycle state — this family MUST be visually and structurally distinct from the Evidence/Confidence and AI color families defined below.
- **FR-023**: The system MUST define a dedicated evidence/confidence color family (distinct hues and/or a distinct visual structure from status colors) used exclusively to represent extraction confidence and evidence-conflict states, never repurposed for workflow status or AI-process signaling.
- **FR-024**: The system MUST define a dedicated AI-signal color family (distinct from both status and evidence/confidence colors) used exclusively to indicate "this content was AI-generated / is an AI process in progress," never repurposed for status or confidence.
- **FR-025**: The system MUST define a constrained, purpose-built data-visualization color palette derived from and compatible with the semantic token set, rejecting generic charting-library default palettes; the same value in a chart MUST carry the same meaning it carries elsewhere in the product (e.g., a risk color in a chart must match the risk color used in a badge).
- **FR-026**: Every semantic, status, evidence/confidence, and AI color token MUST be paired with a defined non-color signal (icon, pattern, or label) for use wherever that token conveys meaning, satisfying the "not color alone" accessibility rule.
- **FR-027**: The system MUST enumerate the complete set of allowed color tokens; introducing a new color anywhere in the product without adding it to this enumerated set first is prohibited (see Future Extensibility).

#### E. Theming: Dark and Light (Topics 24–25)

- **FR-028**: The system MUST define both a light and a dark theme as first-class, independently designed surfaces — not a single theme with an automatically inverted derivative — while sharing the same semantic token names and roles across both.
- **FR-029**: Every semantic token MUST resolve to a specific, deliberately chosen value in both themes, and every such resolution MUST independently satisfy the contrast and non-color-alone accessibility rules in its own theme.
- **FR-030**: The system MUST define which theme is the default for new users and how the choice is persisted, and MUST support switching between themes without a full page reload or loss of in-progress work.
- **FR-031**: Elevation, shadow, and surface treatments MUST be independently tuned for dark theme (e.g., using lightness/border shifts rather than shadow darkening, which is ineffective on dark backgrounds) rather than reusing light-theme shadow values unmodified.

#### F. Responsive Philosophy, Density, White Space (Topics 26–28)

- **FR-032**: The system MUST define a small, fixed set of viewport breakpoints and, for each, which layout adaptations are permitted (e.g., panel collapsing, column reflow) versus which core information/actions must remain available regardless of width.
- **FR-033**: The system MUST state a default information density appropriate for an expert, all-day tool and MUST NOT default to sparse, marketing-site-style whitespace; whitespace MUST be used to group and separate meaning, not to fill space decoratively.
- **FR-034**: The system MUST define minimum touch/click target sizing that holds even at the system's higher-density defaults, ensuring density does not compromise usability or accessibility.

#### G. Iconography & Illustration (Topics 29–30)

- **FR-035**: The system MUST define a single, closed icon library (one visual style, one stroke weight, a fixed set of sizes) used exclusively across the product; icons MUST NOT be sourced ad hoc from multiple stylistically inconsistent sets.
- **FR-036**: Every icon used to convey state or meaning (not purely decorative) MUST have a defined, singular meaning used consistently everywhere it appears — the same icon MUST NOT mean different things on different screens.
- **FR-037**: Illustration use MUST be minimal, purposeful, and non-decorative; the system MUST NOT use mascot characters, playful/whimsical illustration styles, or illustration as a substitute for clear empty/error-state copy (see Design Rationale for why this is a deliberate rejection of common SaaS defaults).

#### H. Motion: Animation Philosophy, Motion Principles, Transitions (Topics 31–33)

- **FR-038**: The system MUST define motion as strictly purposeful — every animation must communicate a state change, spatial relationship, or in-progress process; decorative or "delight" motion with no informational purpose is prohibited.
- **FR-039**: The system MUST define a small, fixed set of motion durations and easing curves, each mapped to a category of transition (e.g., micro-interaction, panel transition, page-level transition), applied consistently by category.
- **FR-040**: All motion durations MUST be short enough not to impede an expert user performing the same interaction hundreds of times per day; the system MUST NOT use motion characteristic of consumer/marketing products (bouncy, elaborate, multi-stage).
- **FR-041**: Every animated transition MUST have a fully specified, non-animated equivalent that is used when the operating system's reduced-motion preference is active, preserving all information the animation conveyed.

#### I. Feedback States: Loading, Skeleton, Empty, Error, Success, Warning, Notification (Topics 34–40)

- **FR-042**: The system MUST define a single, consistent loading-state pattern that appears within 100ms of any data-fetching action, used identically across every view in the product.
- **FR-043**: The system MUST define a skeleton-loading pattern (structural placeholder matching the eventual content's layout) for use where content-shape is known in advance, distinct from and used in place of an indeterminate spinner wherever applicable.
- **FR-044**: The system MUST define a single, consistent empty-state pattern (minimal, information-dense, action-oriented — not illustration-led, per FR-037) used identically across every view that can have zero data.
- **FR-045**: The system MUST define a single, consistent error-state pattern that explains what failed in plain language, offers a retry action where meaningful, and never exposes raw technical detail as the primary message.
- **FR-046**: The system MUST define a single, consistent success-state pattern (confirmation of a completed action) that is visually distinct from, and does not use color or iconography that could be confused with, the AI-signal or evidence/confidence color families.
- **FR-047**: The system MUST define a single, consistent warning-state pattern (a condition requiring attention but not yet a failure) visually distinct from both error and success states, using more than color alone to convey the distinction.
- **FR-048**: The system MUST define a single, consistent notification-design pattern (toast/inline/badge, as applicable) with defined rules for how long a transient notification remains visible, how persistent notifications are distinguished from transient ones, and how multiple simultaneous notifications are stacked or grouped.
- **FR-049**: Every one of the six feedback-state patterns above (loading, skeleton, empty, error, success, warning) MUST be visually distinguishable from every other, even to a user who does not read the accompanying text.

#### J. Overlay Patterns: Dialog, Drawer (Topics 41–42)

- **FR-050**: The system MUST define dialog usage as reserved for genuinely blocking confirmations (e.g., an irreversible action) and MUST NOT be used for routine viewing, editing, or multi-step tasks that a non-blocking panel could handle instead (see Enterprise UX Rules).
- **FR-051**: The system MUST define a drawer/panel pattern for contextual, non-blocking viewing and editing tasks (e.g., inspecting an evidence item without leaving the surrounding application context), including its entry/exit transition, sizing behavior, and stacking rules if more than one can be open.
- **FR-052**: Every dialog MUST have a single, unambiguous primary action and MUST make the safe/non-destructive path (e.g., "Cancel") at least as easy to select as the destructive/confirming path.
- **FR-053**: Every drawer and dialog MUST trap and manage keyboard focus correctly while open and MUST return focus to the triggering element on close (see Focus Management).

#### K. Data Surfaces: Tables, Forms, Search (Topics 43–45)

- **FR-054**: The system MUST define standard table-row height, header treatment, sort-indicator style, and selection-state treatment, applied identically across every table in the product regardless of its data type.
- **FR-055**: The system MUST define standard form-field states (default, focus, filled, invalid, disabled) and standard placement rules for field labels, helper text, and validation error messages, applied identically across every form in the product.
- **FR-056**: The system MUST define a single, consistent search-input pattern (visual treatment, placeholder convention, result-list presentation) used identically everywhere search appears in the product.
- **FR-057**: Table cells and form fields presenting monetary, date, percentage, or identifier values MUST use the typographic and formatting rules defined for those data categories consistently across every table and form.

#### L. Domain-Specific Evidence, AI & Compliance Visual Patterns (Topics 46–54)

- **FR-058**: The system MUST define a single, consistent visual treatment for highlighting the exact region of a source document page corresponding to a piece of evidence, distinguishable from ordinary page content and from a search-match highlight if both exist in the same viewer.
- **FR-059**: The system MUST define a single "evidence chip" pattern (a compact, reusable representation of a citation or evidence reference) used identically wherever an evidence reference appears — in findings, in Copilot citations, in the audit trail — so a user learns its meaning once and recognizes it everywhere.
- **FR-060**: The system MUST define a standard visual structure for presenting a finding, ensuring its five required explainability elements (what, why, evidence, confidence, recommended action — per the platform's explainability requirement) are always presented in the same relative order and visual grouping, never reordered or partially presented per screen.
- **FR-061**: The system MUST define a single confidence-indicator scale (a small, fixed number of bands, e.g., high/medium/low) with a consistent visual encoding (the dedicated evidence/confidence color family plus a non-color signal) used identically everywhere confidence is shown, and MUST NOT allow a different confidence visualization to be introduced per screen or per data type.
- **FR-062**: The system MUST define a standard audit-timeline visual pattern (chronological, immutable-feeling, attributed-and-timestamped entries) used identically wherever a history of events is presented, visually reinforcing that these entries cannot be edited or reordered.
- **FR-063**: The system MUST define design principles for a knowledge-graph/relationship visualization — node and edge visual treatment, a legibility ceiling beyond which the system requires a filtered or list-based fallback view rather than rendering an unreadable dense graph, and a rule that every node remains one action from its full detail.
- **FR-064**: The system MUST define chart design principles (which chart types are permitted for which data shapes, axis and label treatment, and the mandatory use of the constrained data-visualization palette from FR-025) rather than leaving charting decisions to a general-purpose charting library's defaults.
- **FR-065**: The system MUST define a standard risk-indicator visual pattern, distinct from both status colors and confidence colors, used consistently wherever a business/compliance risk level (as opposed to a workflow status or an extraction confidence) is communicated.
- **FR-066**: The system MUST require that any visual pattern representing an AI-generated value or process include a persistent, non-decorative indicator (icon and/or label, from the dedicated AI-signal color family) distinguishing it from human-entered or human-confirmed content, in every context, including print/export (see Edge Cases).

#### M. Accessibility (Topics 55–60)

- **FR-067**: The system MUST require WCAG 2.1 Level AA conformance as the baseline for every component and pattern it defines; no component definition is considered complete without its accessibility behavior specified.
- **FR-068**: The system MUST define the exact minimum contrast ratios required for normal text, large text, and non-text interactive elements, in both light and dark theme, and every color-token pairing in the system MUST be pre-verified against these ratios.
- **FR-069**: The system MUST define a complete keyboard-interaction model (tab order, activation keys, escape/dismiss behavior, arrow-key behavior within composite components like tables and menus) for every interactive component category.
- **FR-070**: The system MUST define a single, consistent focus-indicator treatment (see FR-021) and a focus-management rule set governing what happens to focus when content appears, disappears, or an overlay opens/closes.
- **FR-071**: The system MUST define how every animated pattern in the system degrades under the operating system's reduced-motion preference, with no loss of conveyed information (see FR-041).
- **FR-072**: The system MUST define screen-reader behavior expectations for every non-text-conveyed meaning in the system (icons, color-coded states, dynamic content updates) — every such meaning MUST have an equivalent, announced text alternative.

#### N. Enterprise UX & Cognitive Discipline (Topics 61–65)

- **FR-073**: The system MUST codify a rule against using a blocking modal where a non-blocking panel would serve (see FR-050), against representing the same concept two different visual ways (Core Principle 2), and against introducing decorative elements that do not serve comprehension or task speed.
- **FR-074**: The system MUST define cognitive-load reduction rules, including a limit on simultaneous visual signals a single element may carry (e.g., a table row should not need to communicate more distinct pieces of state than a user can register in a single glance) and a requirement that dense views group related information rather than presenting it as an undifferentiated list.
- **FR-075**: The system MUST define error-prevention rules, including that destructive or hard-to-reverse actions require a distinct confirming step (see FR-052) and that forms validate and communicate problems before allowing an erroneous submission, not only after.
- **FR-076**: The system MUST define progressive-disclosure rules: advanced, infrequently needed detail (e.g., a full relationship graph, a full audit history) MUST be reachable on demand from the primary view rather than shown by default, so routine tasks are not visually crowded by advanced capability.
- **FR-077**: The system MUST define interaction-consistency rules requiring that a given gesture or shortcut (e.g., how to dismiss a panel, how to confirm a destructive action) behaves identically everywhere it is offered in the product.

#### O. System Governance: Components, Naming, Tokens, Extensibility, NFRs (Topics 66–70)

- **FR-078**: The system MUST define, for every component category it recognizes, the complete set of states that category must support (at minimum: default, hover, focus, active, disabled, loading, error, and any domain-specific states such as "AI-generated" or "overridden") before that category may be considered specified.
- **FR-079**: The system MUST define a single, consistent naming convention for tokens, component categories, and states, applied without exception, so that any name in the system is predictable from the convention alone rather than needing to be looked up individually.
- **FR-080**: The system MUST define its token architecture as the authoritative, closed source of every visual value in the product (see FR-018); any value not expressible as an existing token is, by definition, either a gap in the system requiring a formal addition, or an error in the implementation, never a legitimate one-off.
- **FR-081**: The system MUST define a process for proposing, reviewing, and formally adding a new token, component state, or pattern, analogous in rigor to the platform engineering constitution's own amendment procedure, so the system can evolve without fragmenting.
- **FR-082**: The system MUST define non-functional design requirements it imposes on every implementation of it — at minimum, that visual and motion choices must not measurably degrade the interaction performance targets defined by the product's broader non-functional requirements (e.g., no animation or effect may be so heavy it causes perceptible input lag at the product's stated data scale).

### Key Entities *(include if feature involves data)*

- **Design Token**: A named, versioned value (color, spacing step, type-scale step, radius, elevation level, motion duration/easing) organized in two tiers — primitive (raw value) and semantic (role- and meaning-based) — with theme-specific resolutions (light/dark) at the semantic tier.
- **Type Scale Step**: A named combination of size, weight, and line-height mapped to a specific semantic purpose (e.g., "heading.section," "data.tabular"), with defined minimum contrast requirements.
- **Color Role (Semantic Token)**: A named color purpose (e.g., "status.at-risk," "evidence.confidence.low," "ai.signal") belonging to exactly one of the system's distinct color families (semantic/surface/interaction/focus, Status, Evidence/Confidence, AI, Data Visualization), each independently resolved for light and dark theme.
- **Component State**: One entry in the fully enumerated state model (default, hover, focus, active, disabled, loading, error, plus domain-specific states) that every interactive component category must define before it is considered specified.
- **Elevation Level**: A named layer (e.g., base, raised, overlay) with a single corresponding shadow/surface treatment, representing a specific structural meaning, not a decorative choice.
- **Motion Token**: A named duration-and-easing pair mapped to a category of transition (micro-interaction, panel, page-level), with a defined non-animated reduced-motion equivalent.
- **Confidence Level**: One of a small, fixed number of bands (e.g., high/medium/low) with a consistent visual encoding used everywhere extraction confidence is shown.
- **Risk / Status Level**: One of a small, fixed number of bands representing workflow status or business/compliance risk, each visually and structurally distinct from Confidence Levels and from AI-signal indicators.
- **Theme**: A complete, independently designed resolution (light or dark) of every semantic token in the system, sharing token names and roles across both.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Two engineers, given only this specification and no shared visual reference, independently build the same category of new screen and produce results using identical type scale steps, spacing values, and color tokens for equivalent elements.
- **SC-002**: Zero one-off (non-token) color, spacing, radius, or type-size values are found across a full design/code audit of any feature built under this system.
- **SC-003**: 100% of color usage that conveys meaning (status, confidence, risk, AI-origin) is paired with a non-color signal, verified by an audit performed with color perception simulated/removed.
- **SC-004**: 100% of defined text/background token pairings, in both light and dark theme, meet or exceed WCAG AA contrast minimums, verified by automated contrast audit with zero exceptions.
- **SC-005**: 100% of interactive component categories have every required state (default, hover, focus, active, disabled, loading, error) explicitly defined before implementation begins; zero components ship with an improvised, undefined state.
- **SC-006**: A reviewer shown a mixed set of AI-extracted, low-confidence, and human-overridden values with text labels hidden correctly categorizes each using visual treatment alone, at a target accuracy of 100% (this is a safety-critical distinction, not a "good enough" one).
- **SC-007**: A new frontend engineer, given only this specification, can correctly identify the right token or pattern for a stated design need without consulting a designer, in under 5 minutes, for at least 90% of realistic scenarios tested.
- **SC-008**: Automated accessibility audits report zero critical or serious WCAG violations across a representative sample of screens built under this system.
- **SC-009**: All motion in the system, when reduced-motion is enabled, presents its information with zero loss versus the animated version, verified across every defined motion pattern.
- **SC-010**: Enterprise reviewers unfamiliar with the product's origin, shown representative screens, characterize the product as comparable in visual maturity to established enterprise software (the stated Stripe/Linear/GitHub/Bloomberg reference class) rather than as an early-stage or student project, in qualitative review.

---

## Assumptions

- **This specification governs visual and interaction design language only.** It does not define specific screen layouts, page-level compositions, or feature-specific workflows — those belong to feature-level specifications (e.g., the Underwriter Workspace specification) and must comply with, but are not restated by, this system.
- **A single design system serves the entire product**, including any future workspace (e.g., a future Operational Intelligence surface for the Mortgage Operations Manager persona) — this specification is written to be feature-agnostic and durable across the product's lifetime, not scoped to any one feature.
- **Light and dark theme are both mandatory from the outset**, consistent with the product's all-day, expert-user usage pattern (matching VS Code's and Linear's treatment of dark theme as a first-class default, not an afterthought) — a single-theme launch is not assumed.
- **The system assumes a desktop/laptop-first, keyboard-capable primary usage context**, consistent with the Underwriter Workspace specification's own assumptions; touch-first mobile interaction patterns are not defined here and are out of scope.
- **Token values themselves (specific hex codes, specific pixel/rem values, specific font family names) are intentionally not enumerated in this specification.** This document defines the *structure, roles, rules, and constraints* the token set must satisfy (how many steps, what each must accomplish, what must remain distinct from what); the literal value palette is a design-production artifact to be produced against these rules during planning/implementation, not a product-scope decision to be made in this specification.
- **This system does not define specific icon glyphs, specific chart-library choices, or specific illustration assets** — it defines the *rules* those choices must satisfy (a single closed icon style, a constrained data-viz palette, no mascot/decorative illustration), consistent with this being a design language specification, not an asset production spec.

---

## Design Rationale — Challenging Weaker Alternatives

- **Two-tier (primitive → semantic) token architecture, not a flat color/value list.** A flat list of named colors or spacing values (as many early-stage products use) is faster to start with but cannot be re-themed (dark mode becomes a from-scratch redesign) and cannot be safely evolved (changing "blue-500" everywhere it's hardcoded is unsafe; changing what "text.critical" *resolves to* is safe by construction). The two-tier model costs more upfront definition and pays it back completely the first time the system needs to change a value or add a theme — which, for a product with a multi-year regulated lifespan, is not an if but a when.
- **Three structurally distinct color families (Status, Evidence/Confidence, AI) instead of one universal traffic-light scheme.** The weak default — red/amber/green meaning "bad/warning/good" applied everywhere — is exactly wrong for this product, because it collapses three genuinely different meanings ("the AI isn't sure," "there's a business/compliance risk," "the workflow is behind schedule") into a single visual language a rushed reviewer can misread under time pressure. This is not a stylistic preference; conflating these is a direct risk to the explainability guarantee the entire product is built on.
- **Restrained, near-flat elevation over skeuomorphic depth (heavy shadows, glassmorphism, gradients).** Heavy depth effects photograph well in marketing screenshots but reduce legibility and add visual noise at the information density this product requires; Bloomberg Terminal and Linear's near-flat restraint is a deliberate expert-user optimization, not a limitation of older/simpler tooling.
- **No mascot, no whimsical illustration, minimal empty-state decoration.** Illustration-led empty states are a strong pattern for consumer onboarding (where the goal is emotional warmth for a first-time user) and a weak, even irritating, pattern for a tool used by the same expert 6–10 hours a day for years — after the first week, decorative illustration is pure visual cost with no remaining benefit, and it consumes vertical space this product's table- and document-heavy screens cannot spare.
- **A closed, constrained data-visualization palette instead of a general charting library's default categorical colors.** Default chart palettes are designed for generic BI dashboards with no pre-existing color meaning; this product already has color meaning (status, confidence, risk, AI-origin) established elsewhere, and introducing a fourth, incompatible "chart color language" would directly undermine the "one meaning, one representation" principle the moment a chart and a badge appear on the same screen.
- **Motion as fast and purposeful, not delightful.** Bouncy easing, elaborate multi-stage transitions, and other "delightful" motion patterns common in consumer products are a liability, not an asset, at hundreds of repetitions per day — they slow perceived performance, actively conflict with reduced-motion accessibility requirements, and read as informal in a context (bank examiners, compliance reviewers) where informal is a credibility risk.
- **A single closed icon library over "whatever icon looks right" per screen.** Ad hoc, stylistically mismatched icon sets (mixing outline and filled styles, mixing stroke weights) are one of the fastest, most visible tells that distinguish a professionally designed enterprise product from an assembled one — enforcing a single closed set is a small constraint with an outsized credibility payoff.
- **Dialogs reserved strictly for blocking confirmations, not routine editing.** Overusing modal dialogs (a common default in generic admin templates and CRMs) interrupts the reviewer's flow and hides the surrounding evidence context they are actively trying to reason about; a contextual, non-blocking drawer preserves that context and is the stronger enterprise pattern for this product's evidence-first working style.

---

## Non-Functional Design Requirements

- The design system's visual and motion choices MUST NOT measurably degrade the interaction-performance targets defined by the product's functional specifications (e.g., no shadow, blur, or animation effect may be heavy enough to cause perceptible input lag at a scale of 100,000+ records).
- Every token and pattern in the system MUST be defined independently of any specific frontend framework or technology choice, so the system remains valid even if the underlying implementation technology changes over the product's lifetime.
- The system MUST be able to express every screen defined by every current and future feature specification using only its existing tokens and component-state model, or explicitly flag a gap through the extensibility process (FR-081) — it MUST NOT silently tolerate per-feature visual exceptions.
- The system's accessibility, theming, and motion-reduction rules MUST hold simultaneously (e.g., dark theme AND reduced motion AND high contrast, all at once) — these are independent, combinable user preferences, not mutually exclusive configurations that only need to work in isolation.

---

## Future Extensibility

- **Extension process**: A genuinely new visual need (a new component category, a new chart type, a new domain-specific indicator) must first be evaluated against the existing token set and component-state model to confirm no existing pattern already satisfies it; only if none does may a new token, pattern, or state be formally proposed, named per the system's naming conventions, and added to this specification — mirroring the amendment rigor of the platform's own engineering constitution.
- **Versioning**: Changes to this system should be tracked with the same discipline as the platform's engineering constitution (a recorded rationale and impact assessment for every addition or change), so that a future maintainer can understand not just the current state of the system but the reasoning trail that produced it.
- **Anticipated future extension points** (recorded here so they are planned for, not improvised later): a future Operational Intelligence workspace's data-visualization needs (team-wide throughput/SLA charts) should be expected to reuse this system's existing data-visualization and status color rules rather than introducing a parallel visual language; a future native mobile companion, if built, should be expected to require a deliberate, explicit extension of the responsive/density rules rather than a reinterpretation of them; a future embedded/iframe deployment mode (surfacing MIL within a partner LOS's own interface) should be expected to require this system's tokens to be exposed in a way a host application's chrome does not visually conflict with — a consideration for the extension process, not a requirement resolved in this specification.
