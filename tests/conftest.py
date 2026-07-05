"""
Root test configuration — shared fixtures and pytest markers.

This conftest is loaded before all test modules. It registers pytest marks,
configures asyncio mode, and provides fixtures that are available across
all test categories (unit, integration, contract, providers).

Test categories (configured in pyproject.toml [tool.pytest.ini_options]):
  unit         — fast, in-process, no external dependencies
  integration  — require live infrastructure (docker-compose up)
  contract     — validate HTTP responses against OpenAPI contracts
  providers    — conformance tests for provider implementations

Run a specific category:
  pytest tests/unit              — unit tests only
  pytest tests/integration       — integration tests
  pytest -m contract             — all contract-marked tests
"""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Environment guard
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Enforce safe test environment settings."""
    # Prevent tests from accidentally connecting to a production database.
    if os.getenv("MIL_ENV", "development") == "production":
        pytest.exit(
            "Tests must not run against a production environment (MIL_ENV=production detected).",
            returncode=1,
        )
    # Inference is now a real provider (Gemini): ``build_container`` wires it in
    # every environment and fails fast without an API key. Tests that build the
    # container (worker-wiring tests) never call ``infer`` — they only resolve
    # collaborators — so a dummy key satisfies the startup guard without any
    # network access. Set before the first ``get_settings()`` (lru-cached).
    # A real ``GEMINI_API_KEY`` in the environment is respected and not
    # overwritten. The GeminiInferenceProvider's HTTP behaviour is exercised
    # separately against an httpx.MockTransport (tests/providers).
    os.environ.setdefault("GEMINI_API_KEY", "test-dummy-gemini-key")


# ---------------------------------------------------------------------------
# Auto-marking by directory (Sprint 8 — Production Hardening)
#
# No individual test module applies ``@pytest.mark.unit`` etc. by hand — the
# category is entirely determined by which top-level directory under
# ``tests/`` a test lives in. Without this hook, ``pytest -m unit`` (used by
# ``make test-unit`` and CI) silently collected zero tests, which is exactly
# the kind of "CI reports success but validated nothing" failure mode Sprint
# 8 is meant to close.
# ---------------------------------------------------------------------------

_DIRECTORY_MARKERS = {
    "unit": "unit",
    "integration": "integration",
    "contract": "contract",
    "providers": "providers",
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply the marker matching each test's top-level directory under tests/."""
    for item in items:
        parts = item.path.relative_to(config.rootpath / "tests").parts
        if parts and parts[0] in _DIRECTORY_MARKERS:
            item.add_marker(getattr(pytest.mark, _DIRECTORY_MARKERS[parts[0]]))


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mil_env() -> str:
    """Return the test deployment environment label."""
    return os.getenv("MIL_ENV", "development")


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """
    Base URL for the running MIL API.
    Used by contract tests and end-to-end scenarios.

    Override with MIL_API_BASE_URL environment variable when testing
    against a non-default host or port.
    """
    return os.getenv("MIL_API_BASE_URL", "http://localhost:8000")
