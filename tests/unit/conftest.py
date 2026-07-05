"""
Unit test configuration.

Unit tests must not require any external infrastructure. If a test needs a
database, message broker, or object storage, it belongs in tests/integration/.

Fixtures here provide lightweight in-process stubs for bounded context
dependencies. Concrete stub implementations are added here as bounded contexts
are implemented (Sprint 2+).

Network isolation: ``_block_real_network_connections`` (below) enforces the
policy above structurally, not just by convention. Without it, a test that
accidentally exercises real infrastructure (e.g. entering ``TestClient`` as a
context manager, which runs the app's real ASGI lifespan and opens a database
connection) passes silently on any machine that happens to have that
infrastructure running — such as a developer's laptop with `docker-compose up`
— and only fails once it reaches an environment that does not, such as CI.
That is exactly the failure mode this fixture converts into an immediate,
loud, local error, at the moment the illicit connection is attempted, in every
environment identically.
"""

from __future__ import annotations

import socket

import pytest


@pytest.fixture(autouse=True)
def _unit_marker(request: pytest.FixtureRequest) -> None:
    """Auto-apply the 'unit' marker to all tests under tests/unit/."""
    request.node.add_marker(pytest.mark.unit)


def _blocked_connect(
    _self: socket.socket, address: object, *_args: object, **_kwargs: object
) -> int:
    raise RuntimeError(
        f"tests/unit/ attempted a real network connection to {address!r}. "
        "Unit tests must be infrastructure-independent (see this file's "
        "module docstring). If this test genuinely needs live infrastructure "
        "(a database, broker, or external HTTP call), it belongs in "
        "tests/integration/ instead — or, for HTTP, use httpx.MockTransport "
        "as the existing provider conformance tests do."
    )


@pytest.fixture(autouse=True)
def _block_real_network_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Make any real outbound socket connection raise immediately, for every
    test under tests/unit/.

    Scoped to this directory only via conftest autouse discovery — it never
    applies to tests/integration/ (which legitimately uses testcontainers) or
    tests/providers/ (which legitimately talks to httpx.MockTransport, an
    in-memory transport that never opens a socket in the first place, so it
    is unaffected either way).
    """
    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked_connect)
