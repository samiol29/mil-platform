"""Unit tests for mil.portal.auth — portal session token issue/verify."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from mil.kernel.errors import AuthenticationError
from mil.portal.auth import issue_portal_token, verify_portal_token

_SECRET = b"test-secret-key"


class TestIssueAndVerify:
    def test_round_trip(self) -> None:
        account_id, party_id, tenant_id = uuid4(), uuid4(), uuid4()
        token = issue_portal_token(
            account_id=account_id, party_id=party_id, tenant_id=tenant_id, secret=_SECRET
        )
        claims = verify_portal_token(token, _SECRET)
        assert claims.account_id == account_id
        assert claims.party_id == party_id
        assert claims.tenant_id == tenant_id

    def test_token_has_portal_prefix(self) -> None:
        token = issue_portal_token(
            account_id=uuid4(), party_id=uuid4(), tenant_id=uuid4(), secret=_SECRET
        )
        assert token.startswith("portal.")

    def test_wrong_secret_rejected(self) -> None:
        token = issue_portal_token(
            account_id=uuid4(), party_id=uuid4(), tenant_id=uuid4(), secret=_SECRET
        )
        with pytest.raises(AuthenticationError):
            verify_portal_token(token, b"wrong-secret")

    def test_malformed_token_rejected(self) -> None:
        with pytest.raises(AuthenticationError):
            verify_portal_token("not-a-portal-token", _SECRET)

    def test_internal_dev_token_rejected(self) -> None:
        """An internal-staff dev token must never verify as a portal token (spec's own acceptance criterion)."""
        with pytest.raises(AuthenticationError):
            verify_portal_token("dev.eyJzdWIiOiJ4In0=", _SECRET)

    def test_expired_token_rejected(self) -> None:
        token = issue_portal_token(
            account_id=uuid4(),
            party_id=uuid4(),
            tenant_id=uuid4(),
            secret=_SECRET,
            ttl=timedelta(seconds=-1),
        )
        with pytest.raises(AuthenticationError):
            verify_portal_token(token, _SECRET)

    def test_tampered_payload_rejected(self) -> None:
        token = issue_portal_token(
            account_id=uuid4(), party_id=uuid4(), tenant_id=uuid4(), secret=_SECRET
        )
        prefix, payload_and_sig = token.split(".", 1)
        payload, sig = payload_and_sig.split(".", 1)
        tampered = f"{prefix}.{payload}x.{sig}"
        with pytest.raises(AuthenticationError):
            verify_portal_token(tampered, _SECRET)
