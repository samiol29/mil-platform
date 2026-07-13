"""Unit tests for mil.integration.models — LOSConnection/LOSSyncEvent."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.integration.models import LOSConnection, LOSSyncEvent
from mil.kernel.errors import ValidationError


class TestLOSConnection:
    def test_create_defaults_active(self) -> None:
        connection = LOSConnection.create(
            tenant_id=uuid4(), vendor_type="encompass", created_by_user_id=uuid4()
        )
        assert connection.status == "ACTIVE"

    def test_create_rejects_empty_vendor_type(self) -> None:
        with pytest.raises(ValidationError):
            LOSConnection.create(tenant_id=uuid4(), vendor_type="  ", created_by_user_id=uuid4())

    def test_pause_and_resume(self) -> None:
        connection = LOSConnection.create(
            tenant_id=uuid4(), vendor_type="encompass", created_by_user_id=uuid4()
        )
        connection.pause()
        assert connection.status == "PAUSED"
        connection.resume()
        assert connection.status == "ACTIVE"


class TestLOSSyncEvent:
    def test_create_success_event(self) -> None:
        event = LOSSyncEvent.create(
            tenant_id=uuid4(),
            application_id=uuid4(),
            direction="INBOUND",
            outcome="SUCCESS",
            initiated_by_user_id=uuid4(),
            detail={"document_count": 3},
        )
        assert event.outcome == "SUCCESS"
        assert event.error_message is None

    def test_create_rejects_invalid_direction(self) -> None:
        with pytest.raises(ValidationError):
            LOSSyncEvent.create(
                tenant_id=uuid4(),
                application_id=uuid4(),
                direction="SIDEWAYS",
                outcome="SUCCESS",
                initiated_by_user_id=uuid4(),
            )

    def test_create_rejects_invalid_outcome(self) -> None:
        with pytest.raises(ValidationError):
            LOSSyncEvent.create(
                tenant_id=uuid4(),
                application_id=uuid4(),
                direction="INBOUND",
                outcome="MAYBE",
                initiated_by_user_id=uuid4(),
            )
