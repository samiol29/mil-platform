"""Cross-Application Intelligence bounded context (spec 005-enterprise-
platform §6, Wave 3).

Reasons across a borrower's linked applications (resolved by
``mil.borrower_identity``) to surface **observations**, never decisions
(Constitution Principle I applies to this module exactly as it does to
Findings and Borrower Identity matching). Every observation cites its
supporting evidence (application/document/finding ids) and states plainly
why it exists — no black-box scoring (Principle III).

Grounded in real, already-stored fields only — nothing here is inferred
without evidence backing it (Principle II):

- **Reused documents**: ``Document.contentHash`` collisions across more
  than one application (the same file, or a byte-identical copy,
  uploaded to two different applications).
- **Repeated finding types**: ``Finding.findingType`` values that recur
  across more than one of the borrower's applications.
- **Prior review outcomes**: counts of verified/overridden/escalated
  findings across the borrower's applications, so a reviewer can see
  the borrower's review history at a glance.

Explicitly out of scope, and disclosed as such rather than fabricated:
repeated employer changes, income inconsistencies, and any other signal
that would require semantic/NLP analysis of document content — no such
analysis is built anywhere in this platform today.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library. Inputs are plain dataclasses (``DocumentSignal``/``FindingSignal``)
supplied by the caller — this module never imports ``mil.document``,
``mil.finding``, or ``mil.borrower_identity``. The composition that
resolves a borrower's linked applications to real documents/findings and
calls this module's pure functions lives in ``mil.api.deps``, matching the
pattern already established by every other Wave 2/3 composition class.
"""
