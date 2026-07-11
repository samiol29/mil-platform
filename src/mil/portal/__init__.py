"""Customer Portal bounded context (spec 005-enterprise-platform §12, Wave 4).

Gives borrowers a limited, self-service surface to fulfill document
requests and check status — the platform's first genuinely **external**,
unauthenticated-until-login user population, engineered as a distinct
trust boundary from every internal staff role (Constitution Principle I,
applied with maximum force: a borrower never sees a Finding, Evidence,
Policy result, internal comment, or Timeline/Audit detail; Principle V,
Zero Trust: portal sessions are verified by a dedicated auth realm, never
internal RBAC).

Two entities:

- ``PortalAccount`` — a borrower's portal identity, tied to exactly one
  ``Party`` (never a new borrower-identity concept competing with §5's
  ``BorrowerIdentity``). Email is stored hashed only
  (``email_hash``, mirroring ``identity.User.email_hash``'s exact
  discipline) — never plaintext, since MIL does not store borrower PII.
- ``DocumentChecklistItem`` — one document request against an application
  (optionally scoped to a specific party), created by an Underwriter/RM,
  fulfilled when a borrower uploads a matching document through the
  existing upload contract.

Portal session verification (``mil.portal.auth``) is a self-contained
HMAC-based token scheme, signed with a dedicated
``Settings.mil_portal_secret_key`` — genuinely separate key material from
internal staff auth, so a verification bug in one can never be confused
with the other (spec's own explicit non-negotiable: "never sharing
session/token infrastructure with internal staff authentication").
Portal accounts are never evaluated through ``mil.kernel.security``'s
``Role``/``Permission``/``has_permission`` system.

Schema: ``portal`` PostgreSQL schema (a correction from the spec's original
``core.document_checklist_items`` placement — see the spec's own §12
implementation-correction note for why: aligning with every other Wave 2/3
module's own-schema convention, not the original MVP's ``core`` schema).

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library. References to ``Party``/``MortgageApplication``/``Document`` are
plain UUIDs, never model imports — composition with those bounded contexts
(e.g. resolving a checklist item's application, or triggering the real
document upload path) lives in ``mil.api.deps``, matching the pattern
already established by every other Wave 2/3 composition class.
"""
