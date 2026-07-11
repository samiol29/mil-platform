"""
Customer Portal session token issuance/verification (spec 005-enterprise-
platform §12, Wave 4).

Deliberately self-contained and separate from ``mil.identity.provider``'s
internal-staff token verification — a genuinely distinct trust boundary,
not a shared-secret convenience (the spec's own explicit non-negotiable).
An HMAC-signed opaque token, mirroring the existing platform's stated
preference for simple, explicit mechanisms over external dependencies
(``DevBearerIdentityProvider``'s own base64-JSON precedent) while adding a
real signature — a portal token cannot be forged without
``Settings.mil_portal_secret_key``, and a bug in internal token
verification (``mil.identity.provider``) can never accidentally accept a
portal token or vice versa, since the two verifiers share no code, no
claim shape, and no key material.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from mil.kernel.errors import AuthenticationError

_TOKEN_PREFIX = "portal."
_DEFAULT_TTL = timedelta(hours=12)


@dataclass(frozen=True)
class PortalSessionClaims:
    """Normalized claims carried by a verified portal session token."""

    account_id: UUID
    party_id: UUID
    tenant_id: UUID


def _sign(payload: bytes, secret: bytes) -> str:
    signature = hmac.new(secret, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")


def issue_portal_token(
    *,
    account_id: UUID,
    party_id: UUID,
    tenant_id: UUID,
    secret: bytes,
    ttl: timedelta = _DEFAULT_TTL,
) -> str:
    """Issue a signed, time-limited portal session token."""
    now = datetime.now(UTC)
    claims = {
        "account_id": str(account_id),
        "party_id": str(party_id),
        "tenant_id": str(tenant_id),
        "iat": now.isoformat(),
        "exp": (now + ttl).isoformat(),
    }
    payload = (
        base64.urlsafe_b64encode(json.dumps(claims).encode("utf-8")).decode("ascii").rstrip("=")
    )
    signature = _sign(payload.encode("ascii"), secret)
    return f"{_TOKEN_PREFIX}{payload}.{signature}"


def verify_portal_token(token: str, secret: bytes) -> PortalSessionClaims:
    """
    Verify a portal session token's signature and expiry, returning its
    claims. Raises ``AuthenticationError`` on any failure — malformed
    token, bad signature, or expiry — never distinguishing the reason to
    the caller (standard authentication-failure discipline).
    """
    if not token.startswith(_TOKEN_PREFIX):
        raise AuthenticationError("Invalid portal session token")
    body = token[len(_TOKEN_PREFIX) :]
    try:
        payload, signature = body.split(".", 1)
    except ValueError as exc:
        raise AuthenticationError("Invalid portal session token") from exc

    expected_signature = _sign(payload.encode("ascii"), secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise AuthenticationError("Invalid portal session token")

    try:
        padded = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        exp = datetime.fromisoformat(claims["exp"])
        if datetime.now(UTC) > exp:
            raise AuthenticationError("Portal session token has expired")
        return PortalSessionClaims(
            account_id=UUID(claims["account_id"]),
            party_id=UUID(claims["party_id"]),
            tenant_id=UUID(claims["tenant_id"]),
        )
    except AuthenticationError:
        raise
    except Exception as exc:
        raise AuthenticationError("Invalid portal session token") from exc
