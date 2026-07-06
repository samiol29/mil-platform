"""
Cross-bounded-context ORM model registration.

SQLAlchemy resolves a mapped class's foreign keys (and topologically sorts
tables for DDL/flush ordering) lazily, the first time something needs it —
and only against whichever tables have actually been imported (registered on
the shared ``Base.metadata``) by that point in the process's lifetime. A
process that has only imported the bounded contexts its *own* code path
happens to touch can flush a row whose FK targets a table from a bounded
context nothing else imported yet, and hit
``sqlalchemy.exc.NoReferencedTableError`` — not at import time, but the first
time a specific write path is exercised, making it a heisenbug tied to
request/job ordering rather than a reliable startup failure.

This is a **sanctioned exception** to every bounded context's own dependency
rule (each of ``mil.<context>`` imports only ``mil.kernel``, its own package,
and the stdlib): this one function imports every bounded context's
``models.py`` purely for the ORM registration side effect, never touching
business logic. Both worker processes (``workers.bootstrap
.build_worker_context``) and the API process (``main.create_app``) call
``register_all_models()`` during startup so neither depends on the other, or
on the accident of which routers/handlers happen to transitively import
which model modules.
"""

from __future__ import annotations


def register_all_models() -> None:
    """Import every bounded context's ``models.py`` to register its tables."""
    from mil.application import models as _application_models  # noqa: F401
    from mil.audit import models as _audit_models  # noqa: F401
    from mil.copilot import models as _copilot_models  # noqa: F401
    from mil.document import models as _document_models  # noqa: F401
    from mil.document import ocr_models as _document_ocr_models  # noqa: F401
    from mil.evidence import models as _evidence_models  # noqa: F401
    from mil.finding import models as _finding_models  # noqa: F401
    from mil.identity import models as _identity_models  # noqa: F401
    from mil.orchestrator import models as _orchestrator_models  # noqa: F401
    from mil.outbox import models as _outbox_models  # noqa: F401
    from mil.policy import models as _policy_models  # noqa: F401
    from mil.review import models as _review_models  # noqa: F401
