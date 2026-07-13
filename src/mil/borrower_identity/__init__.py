"""Borrower Identity Resolution bounded context (spec 005-enterprise-platform
§5, Wave 3).

Resolves when multiple ``Party`` rows (across different applications)
represent the same real-world borrower. Never merges automatically — every
match is advisory (``IdentityMatchCandidate``) until a human confirms it
(Constitution Principle I, applied to identity exactly as to Findings).

Matching signals, both grounded in real, already-stored data (nothing here
requires storing SSN/DOB/address/phone/email in MIL — Principle V; ``Party``
carries only ``display_name`` and, additively, a hashed external
identifier):

- **Deterministic**: an exact match on ``Party.external_identifier_hash``
  (same hash, same identifier type) — high confidence.
- **Probabilistic**: normalized ``display_name`` similarity — the only
  other real signal available. No DOB/address/phone/email matching is
  implemented because MIL does not store those fields (confirmed by direct
  inspection of ``mil.application.models.Party`` before this module was
  written) — implementing it would mean fabricating data MIL deliberately
  never collects.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library. References to ``Party``/``MortgageApplication`` are plain UUIDs,
never model imports — the composition that resolves those ids to real
objects lives in the API route layer (``mil.api.deps``), matching the
pattern already established by ``mil.assignment``/``mil.integration``.
"""
