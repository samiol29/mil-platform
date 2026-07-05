"""
Unit tests for ``mil.identity.dev_seed`` — development bootstrap seed.

Exercises ``seed_development_identity`` against a real (in-memory SQLite)
database rather than mocks, since the defect it fixes (a foreign key
violation against an unseeded ``core.users`` row) only reproduces against a
real ORM/database round trip.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mil.identity.dev_seed import seed_development_identity
from mil.identity.models import User
from mil.identity.provider import DEV_TENANT_ID, DEV_USER_ID
from mil.kernel.db import Base

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    # SQLite has no concept of Postgres schemas; translate away every schema
    # registered on Base.metadata (not just "core") so this test is unaffected
    # by which other bounded-context models happen to already be imported
    # elsewhere in the test session.
    schemas = {table.schema for table in Base.metadata.tables.values() if table.schema}
    engine = create_engine(
        "sqlite:///:memory:",
        execution_options={"schema_translate_map": dict.fromkeys(schemas)},
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autocommit=False, autoflush=False)
    engine.dispose()


class TestSeedDevelopmentIdentity:
    def test_creates_dev_user_on_first_run(self, session_factory: sessionmaker[Session]) -> None:
        seed_development_identity(session_factory)

        with session_factory() as session:
            user = session.get(User, DEV_USER_ID)
            assert user is not None
            assert user.tenant_id == DEV_TENANT_ID
            assert user.is_active is True
            assert user.display_name == "Dev Admin"

    def test_idempotent_on_repeated_calls(self, session_factory: sessionmaker[Session]) -> None:
        seed_development_identity(session_factory)
        seed_development_identity(session_factory)  # must not raise

        with session_factory() as session:
            count = session.query(User).filter(User.id == DEV_USER_ID).count()
            assert count == 1

    def test_does_not_touch_other_users(self, session_factory: sessionmaker[Session]) -> None:
        from uuid import uuid4

        with session_factory() as session:
            session.add(
                User(
                    id=uuid4(),
                    tenant_id=uuid4(),
                    external_identity_id="someone-else",
                    email_hash="a" * 64,
                    display_name="Someone Else",
                    is_active=True,
                )
            )
            session.commit()

        seed_development_identity(session_factory)

        with session_factory() as session:
            assert session.query(User).count() == 2
