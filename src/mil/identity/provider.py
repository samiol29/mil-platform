"""
External Identity Provider (IdP) integration for the MIL Platform.

This module defines the abstraction layer between the platform and
external identity systems (OIDC providers, enterprise SSO, etc.).

Design:

- ``TokenClaims`` — a platform-normalised representation of the decoded
  claims from any IdP token.  This decouples the rest of the platform
  from IdP-specific claim names or formats.

- ``IdentityProvider`` — abstract base class defining the contract for
  token validation.  A concrete implementation is registered in the DI
  container at startup.

- ``DevIdentityProvider`` — a development-only implementation that
  accepts a simple base64-encoded JSON token.  It requires no external
  dependencies and no network access, making it suitable for local
  development and unit testing.

  Development tokens are JSON objects base64-encoded and prefixed with
  ``dev.`` to make them visually distinct from real JWTs::

      import base64, json
      claims = {"sub": "dev-001", "tid": "<tenant-uuid>",
                "roles": ["VERIFICATION_OFFICER"],
                "email": "dev@example.com", "display_name": "Dev User"}
      token = "dev." + base64.b64encode(json.dumps(claims).encode()).decode()

- ``populate_authenticated_user`` — converts a ``TokenClaims`` object to
  the platform's ``AuthenticatedUser`` context type.

- ``IdentityProviderError`` — raised when token validation fails.

Security note: ``DevIdentityProvider`` MUST NOT be registered in staging
or production containers.  The ``IdentityProvider`` resolved from the DI
container should be an OIDC-backed implementation in those environments.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.  No bounded context may be imported here.
"""

from __future__ import annotations

import abc
import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from mil.kernel.errors import AuthenticationError
from mil.kernel.security import AuthenticatedUser, Role
from mil.kernel.types import TenantId, UserId

# ---------------------------------------------------------------------------
# Token claims (normalised across IdPs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenClaims:
    """
    Platform-normalised claims decoded from an identity token.

    These fields are the minimal set the platform requires.  Concrete
    ``IdentityProvider`` implementations are responsible for mapping from
    IdP-specific claim names (e.g. ``sub``, ``oid``, ``preferred_username``)
    to this normalised structure.

    Attributes:
        subject: The IdP-assigned stable identifier for the user
            (``sub`` claim in OIDC).
        tenant_id: The platform tenant UUID extracted from the token
            (e.g. from a custom ``tid`` claim or the token audience).
        roles: RBAC roles granted to this user, matching the string
            constants in ``mil.kernel.security.Role``.
        email: The user's email address.  May be empty if the IdP does
            not provide it.
        display_name: Human-readable name for audit trails and UI.
        issued_at: UTC timestamp when the token was issued.
        expires_at: UTC timestamp when the token expires.  The provider
            must reject tokens that have expired.
    """

    subject: str
    tenant_id: TenantId
    roles: frozenset[str] = field(default_factory=frozenset)
    email: str = ""
    display_name: str = ""
    issued_at: datetime | None = None
    expires_at: datetime | None = None


# ---------------------------------------------------------------------------
# Abstract IdP interface
# ---------------------------------------------------------------------------


class IdentityProvider(abc.ABC):
    """
    Abstract interface for external identity provider integration.

    The single method ``validate_token`` accepts an opaque token string
    and returns normalised ``TokenClaims`` on success.  It raises
    ``AuthenticationError`` on any validation failure (expired, tampered,
    unknown issuer, etc.).

    Concrete implementations handle IdP-specific details:
    - OIDC: fetch JWKS, verify signature, validate ``iss`` and ``aud``.
    - SAML: verify assertion signature, extract attributes.
    - Dev: parse base64-JSON, skip cryptographic verification.
    """

    @abc.abstractmethod
    def validate_token(self, token: str) -> TokenClaims:
        """
        Validate ``token`` and return normalised claims.

        Args:
            token: The raw bearer token string from the Authorization header.

        Returns:
            ``TokenClaims`` extracted from the validated token.

        Raises:
            AuthenticationError: If the token is invalid, expired,
                tampered, or from an untrusted issuer.
        """


# ---------------------------------------------------------------------------
# Development implementation
# ---------------------------------------------------------------------------


class DevIdentityProvider(IdentityProvider):
    """
    Development-only identity provider that accepts base64-encoded JSON tokens.

    Tokens are ``"dev." + base64(json_payload)``.  No signature verification
    is performed.  This implementation is intentionally trivial so that local
    development and unit tests have a zero-dependency, zero-configuration
    way to produce authenticated requests.

    Accepted token payload fields::

        {
            "sub":          "<subject>",         # required
            "tid":          "<tenant-uuid>",      # required
            "roles":        ["ROLE_NAME", ...],   # optional, default []
            "email":        "user@example.com",   # optional
            "display_name": "User Name",          # optional
            "iat":          1234567890,            # optional (unix timestamp)
            "exp":          9999999999            # optional (unix timestamp)
        }

    MUST NOT be registered in staging or production containers.
    """

    _TOKEN_PREFIX = "dev."

    def validate_token(self, token: str) -> TokenClaims:
        """
        Parse and return claims from a development token.

        Raises:
            AuthenticationError: If the token is not a valid dev token or
                is missing required fields.
        """
        if not token.startswith(self._TOKEN_PREFIX):
            raise AuthenticationError("DevIdentityProvider: token must be prefixed with 'dev.'")

        payload_b64 = token[len(self._TOKEN_PREFIX) :]
        try:
            payload_bytes = base64.b64decode(payload_b64 + "==")  # tolerant padding
            payload: dict[str, object] = json.loads(payload_bytes)
        except Exception as exc:
            raise AuthenticationError(
                "DevIdentityProvider: token payload is not valid base64-encoded JSON"
            ) from exc

        subject = payload.get("sub")
        if not subject or not isinstance(subject, str):
            raise AuthenticationError("DevIdentityProvider: token missing required field 'sub'")

        raw_tid = payload.get("tid")
        if not raw_tid or not isinstance(raw_tid, str):
            raise AuthenticationError("DevIdentityProvider: token missing required field 'tid'")
        try:
            tenant_id = TenantId(UUID(raw_tid))
        except ValueError as exc:
            raise AuthenticationError(
                f"DevIdentityProvider: 'tid' is not a valid UUID: {raw_tid!r}"
            ) from exc

        raw_roles = payload.get("roles", [])
        if not isinstance(raw_roles, list):
            raise AuthenticationError("DevIdentityProvider: 'roles' must be a list")
        roles: frozenset[str] = frozenset(str(r) for r in raw_roles)

        email = str(payload.get("email", ""))
        display_name = str(payload.get("display_name", ""))

        issued_at: datetime | None = None
        expires_at: datetime | None = None
        raw_iat = payload.get("iat")
        raw_exp = payload.get("exp")
        if isinstance(raw_iat, (int, float)):
            issued_at = datetime.fromtimestamp(raw_iat, tz=UTC)
        if isinstance(raw_exp, (int, float)):
            expires_at = datetime.fromtimestamp(raw_exp, tz=UTC)
            if expires_at < datetime.now(UTC):
                raise AuthenticationError("DevIdentityProvider: token has expired")

        return TokenClaims(
            subject=subject,
            tenant_id=tenant_id,
            roles=roles,
            email=email,
            display_name=display_name,
            issued_at=issued_at,
            expires_at=expires_at,
        )


# ---------------------------------------------------------------------------
# AuthenticatedUser population
# ---------------------------------------------------------------------------


def populate_authenticated_user(
    claims: TokenClaims,
    *,
    user_id: UserId,
) -> AuthenticatedUser:
    """
    Convert ``TokenClaims`` to the platform's ``AuthenticatedUser`` context.

    The ``user_id`` parameter is the MIL-internal user UUID, which is
    resolved by the identity repository after the token is validated.
    It is separate from ``TokenClaims.subject`` (the IdP's external
    identifier) because the platform uses stable internal UUIDs as
    primary keys.

    Called by the Zero Trust authentication middleware after:
    1. Extracting the bearer token from the Authorization header.
    2. Calling ``IdentityProvider.validate_token(token)`` to get claims.
    3. Looking up or provisioning the ``User`` record in the database.
    4. Loading the user's active role assignments.

    Args:
        claims: Normalised claims returned by the identity provider.
        user_id: The MIL-internal UUID of the user (from ``core.users``).

    Returns:
        An immutable ``AuthenticatedUser`` ready to be stored in the
        request context variable via ``set_current_user()``.
    """
    return AuthenticatedUser(
        user_id=user_id,
        tenant_id=claims.tenant_id,
        roles=claims.roles,
        email=claims.email,
        display_name=claims.display_name,
    )


# ---------------------------------------------------------------------------
# Development bearer provider — the API's current dev authentication, expressed
# through the IdentityProvider abstraction (Backend Freeze Patch v1.0)
# ---------------------------------------------------------------------------

# Built-in development principal, returned for the literal ``"dev"`` token.
_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
_DEV_TENANT_ID = UUID("00000000-0000-0000-0000-000000000002")


class DevBearerIdentityProvider(IdentityProvider):
    """
    Development ``IdentityProvider`` for the platform's REST API.

    This reproduces exactly the development authentication the API has always
    accepted, now expressed through the ``IdentityProvider`` abstraction so
    that ``mil.api.deps.get_current_user`` resolves its verifier from the DI
    container rather than hard-coding an unsigned token decode. It accepts:

    - the literal token ``"dev"`` — resolves to a built-in ADMIN development
      principal, for zero-configuration local use; and
    - a Base64URL-encoded JSON object carrying ``user_id``, ``tenant_id`` and
      optionally ``roles``/``email``/``display_name`` — the format the API
      test-suite and local tooling already produce.

    **No cryptographic signature is verified.** This provider is a development
    convenience and MUST NOT be registered in staging or production. Non-dev
    environments require a signature-verifying (e.g. OIDC/JWKS) implementation;
    ``build_container`` refuses to start a non-development process that has no
    such provider registered (Backend Freeze Patch v1.0).
    """

    _DEV_TOKEN = "dev"  # sentinel token, not a credential

    def validate_token(self, token: str) -> TokenClaims:
        """Decode a development bearer token into normalised ``TokenClaims``."""
        if token == self._DEV_TOKEN:
            return TokenClaims(
                subject=str(_DEV_USER_ID),
                tenant_id=TenantId(_DEV_TENANT_ID),
                roles=frozenset({Role.ADMIN}),
                email="dev@mil.local",
                display_name="Dev Admin",
            )

        try:
            # Re-add Base64 padding that callers may have stripped.
            padded = token + "=" * (-len(token) % 4)
            raw = base64.urlsafe_b64decode(padded)
            payload: dict[str, object] = json.loads(raw)
        except Exception as exc:
            raise AuthenticationError("Invalid bearer token: cannot decode.") from exc

        try:
            user_id = UUID(str(payload["user_id"]))
            tenant_id = UUID(str(payload["tenant_id"]))
        except (KeyError, ValueError) as exc:
            raise AuthenticationError("Invalid bearer token: missing required field.") from exc

        raw_roles = payload.get("roles", [])
        roles = frozenset(str(r) for r in (raw_roles if isinstance(raw_roles, list) else []))

        return TokenClaims(
            subject=str(user_id),
            tenant_id=TenantId(tenant_id),
            roles=roles,
            email=str(payload.get("email", "")),
            display_name=str(payload.get("display_name", "")),
        )
