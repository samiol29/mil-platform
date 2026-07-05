"""
Development bootstrap seed for the Identity bounded context.

``DevBearerIdentityProvider`` (see ``mil.identity.provider``) authenticates a
built-in development principal — user ``DEV_USER_ID`` in tenant
``DEV_TENANT_ID`` — without ever touching the database. Several tables
(e.g. ``core.applications.created_by``) carry a foreign key to
``core.users.id``, so any write made by that principal fails with a foreign
key violation unless a matching ``core.users`` row already exists.

``seed_development_identity`` closes that gap by ensuring the row exists.
It is:

- **idempotent** — safe to run on every startup; it is a no-op once the row
  exists;
- **development-only** — callers must gate the call on
  ``settings.is_development()`` (see ``main.lifespan``); production and
  staging never run it, matching the fail-fast posture of
  ``mil.kernel.container.build_container`` (no development principal is
  ever authenticated outside development in the first place); and
- **not a schema change** — it seeds a row through the existing ORM model,
  it does not introduce a migration, a tenants table, or new business logic.

Dependency rule: this module imports from ``mil.identity`` (its own bounded
context), ``mil.kernel``, SQLAlchemy, and the Python standard library only.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from mil.identity.models import User
from mil.identity.provider import DEV_TENANT_ID, DEV_USER_ID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

_DEV_EMAIL = "dev@mil.local"
_DEV_DISPLAY_NAME = "Dev Admin"
_DEV_EXTERNAL_IDENTITY_ID = "dev-bootstrap"


def seed_development_identity(session_factory: sessionmaker[Session]) -> None:
    """
    Ensure the built-in development user exists in ``core.users``.

    Matches the principal ``DevBearerIdentityProvider`` authenticates for the
    literal ``"dev"`` bearer token, so that requests made with ``Bearer dev``
    can satisfy foreign keys (e.g. ``applications.created_by``) on first use
    of a freshly migrated development database.

    Safe to call on every application startup: if the row already exists this
    is a no-op. The ``IntegrityError`` guard covers the narrow race where two
    processes seed concurrently against the same database.
    """
    with session_factory() as session:
        if session.get(User, DEV_USER_ID) is not None:
            return

        session.add(
            User(
                id=DEV_USER_ID,
                tenant_id=DEV_TENANT_ID,
                external_identity_id=_DEV_EXTERNAL_IDENTITY_ID,
                email_hash=hashlib.sha256(_DEV_EMAIL.encode("utf-8")).hexdigest(),
                display_name=_DEV_DISPLAY_NAME,
                is_active=True,
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
