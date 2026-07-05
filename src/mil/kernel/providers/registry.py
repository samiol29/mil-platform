"""
ProviderRegistry for the MIL Platform.

The ``ProviderRegistry`` is the single, type-safe façade through which the
Platform Kernel exposes all registered provider implementations to bounded
context code.

Design rationale:

- Bounded context services MUST NOT import concrete provider classes.  They
  resolve ``ProviderRegistry`` from the DI container and call the typed
  accessor methods.
- The registry validates that all required providers are present before the
  application accepts traffic, surfacing missing registrations at startup
  rather than at first use.
- The registry is registered as a singleton in the DI container by
  ``build_container()``.

Provider registration is performed in ``build_container()`` where the
appropriate concrete implementations are instantiated from the deployment
configuration (``Settings``) and registered before the container is returned.

Dependency rule: this module imports only from ``mil.kernel.providers`` and
the Python standard library.  No bounded context code should be imported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from mil.kernel.providers.extraction import ExtractionProvider
    from mil.kernel.providers.inference import InferenceProvider
    from mil.kernel.providers.los_adapter import LOSAdapter
    from mil.kernel.providers.ocr import OCRProvider
    from mil.kernel.providers.policy import PolicyProvider
    from mil.kernel.providers.storage import StorageProvider

_T = TypeVar("_T")

# Registry key constants — used in validation and reporting.
_KEY_OCR = "ocr"
_KEY_EXTRACTION = "extraction"
_KEY_INFERENCE = "inference"
_KEY_POLICY = "policy"
_KEY_STORAGE = "storage"
_KEY_LOS_ADAPTER = "los_adapter"

# Providers that must be registered before the platform starts.
_REQUIRED_PROVIDERS: frozenset[str] = frozenset(
    {_KEY_OCR, _KEY_EXTRACTION, _KEY_INFERENCE, _KEY_POLICY, _KEY_STORAGE}
)
# _KEY_LOS_ADAPTER is optional — some deployments do not use a LOS integration.


class ProviderRegistryError(Exception):
    """Raised when a required provider is missing or registry validation fails."""


class ProviderRegistry:
    """
    Type-safe registry of all platform provider implementations.

    Providers are registered once at startup by ``build_container()`` using
    the ``register_*`` methods, then resolved by bounded context services
    via the ``get_*`` accessors.

    The registry is intentionally not a subclass of the DI ``Container`` — it
    is a higher-level object that holds *typed* provider references and
    enforces the provider contract (version present, etc.) at registration time.

    Lifecycle:

    1. ``build_container()`` creates a ``ProviderRegistry`` instance.
    2. ``build_container()`` calls ``register_*`` for each configured provider.
    3. ``build_container()`` calls ``validate()`` to assert required providers present.
    4. The registry instance is registered as a singleton in the DI container.
    5. Services resolve ``ProviderRegistry`` and call ``get_*()``.
    """

    def __init__(self) -> None:
        self._providers: dict[str, object] = {}

    # ---- Registration -------------------------------------------------------

    def _register(self, key: str, provider: object) -> None:
        """
        Register ``provider`` under ``key``.

        Raises:
            ProviderRegistryError: If a provider is already registered under
                ``key``. Silently overwriting a provider registration would
                hide a configuration bug (e.g. ``build_container`` calling a
                ``register_*`` method twice) — Sprint 8 (Production
                Hardening) requires this to fail fast instead.
        """
        if key in self._providers:
            raise ProviderRegistryError(
                f"Provider already registered for {key!r}: "
                f"{type(self._providers[key]).__name__}. Duplicate provider "
                "registration is not permitted."
            )
        self._providers[key] = provider

    def register_ocr(self, provider: OCRProvider) -> None:
        """Register the active ``OCRProvider`` implementation."""
        self._register(_KEY_OCR, provider)

    def register_extraction(self, provider: ExtractionProvider) -> None:
        """Register the active ``ExtractionProvider`` implementation."""
        self._register(_KEY_EXTRACTION, provider)

    def register_inference(self, provider: InferenceProvider) -> None:
        """Register the active ``InferenceProvider`` implementation."""
        self._register(_KEY_INFERENCE, provider)

    def register_policy(self, provider: PolicyProvider) -> None:
        """Register the active ``PolicyProvider`` implementation."""
        self._register(_KEY_POLICY, provider)

    def register_storage(self, provider: StorageProvider) -> None:
        """Register the active ``StorageProvider`` implementation."""
        self._register(_KEY_STORAGE, provider)

    def register_los_adapter(self, provider: LOSAdapter) -> None:
        """Register the active ``LOSAdapter`` implementation (optional)."""
        self._register(_KEY_LOS_ADAPTER, provider)

    # ---- Accessors ----------------------------------------------------------

    def get_ocr(self) -> OCRProvider:
        """
        Resolve the registered ``OCRProvider``.

        Raises:
            ProviderRegistryError: If no ``OCRProvider`` is registered.
        """
        from mil.kernel.providers.ocr import OCRProvider

        return self._get(_KEY_OCR, OCRProvider)  # type: ignore[type-abstract]

    def get_extraction(self) -> ExtractionProvider:
        """
        Resolve the registered ``ExtractionProvider``.

        Raises:
            ProviderRegistryError: If no ``ExtractionProvider`` is registered.
        """
        from mil.kernel.providers.extraction import ExtractionProvider

        return self._get(_KEY_EXTRACTION, ExtractionProvider)  # type: ignore[type-abstract]

    def get_inference(self) -> InferenceProvider:
        """
        Resolve the registered ``InferenceProvider``.

        Raises:
            ProviderRegistryError: If no ``InferenceProvider`` is registered.
        """
        from mil.kernel.providers.inference import InferenceProvider

        return self._get(_KEY_INFERENCE, InferenceProvider)  # type: ignore[type-abstract]

    def get_policy(self) -> PolicyProvider:
        """
        Resolve the registered ``PolicyProvider``.

        Raises:
            ProviderRegistryError: If no ``PolicyProvider`` is registered.
        """
        from mil.kernel.providers.policy import PolicyProvider

        return self._get(_KEY_POLICY, PolicyProvider)  # type: ignore[type-abstract]

    def get_storage(self) -> StorageProvider:
        """
        Resolve the registered ``StorageProvider``.

        Raises:
            ProviderRegistryError: If no ``StorageProvider`` is registered.
        """
        from mil.kernel.providers.storage import StorageProvider

        return self._get(_KEY_STORAGE, StorageProvider)  # type: ignore[type-abstract]

    def get_los_adapter(self) -> LOSAdapter:
        """
        Resolve the registered ``LOSAdapter``.

        Raises:
            ProviderRegistryError: If no ``LOSAdapter`` is registered.
        """
        from mil.kernel.providers.los_adapter import LOSAdapter

        return self._get(_KEY_LOS_ADAPTER, LOSAdapter)  # type: ignore[type-abstract]

    # ---- Validation ---------------------------------------------------------

    def validate(self, required: frozenset[str] | None = None) -> None:
        """
        Assert that all required providers are registered.

        Args:
            required: Set of provider keys to validate.  Defaults to
                      ``_REQUIRED_PROVIDERS`` (OCR, Extraction, Inference, Storage).
                      ``LOSAdapter`` is optional and not validated unless
                      explicitly included in ``required``.

        Raises:
            ProviderRegistryError: Listing all missing providers.
        """
        keys_to_check = required if required is not None else _REQUIRED_PROVIDERS
        missing = sorted(keys_to_check - self._providers.keys())
        if missing:
            raise ProviderRegistryError(
                f"Required providers not registered: {', '.join(missing)}. "
                "Ensure build_container() registers all providers before "
                "the application starts."
            )

    def is_registered(self, key: str) -> bool:
        """Return ``True`` if a provider is registered under ``key``."""
        return key in self._providers

    def registered_providers(self) -> dict[str, str]:
        """
        Return a mapping of provider key → implementation class name.

        Useful for startup logging and health checks.
        """
        return {key: type(provider).__name__ for key, provider in self._providers.items()}

    # ---- Internal -----------------------------------------------------------

    def _get(self, key: str, expected_type: type[_T]) -> _T:
        # expected_type is imported inside each get_*() method (not at module
        # top-level) to break the import cycle: registry.py is part of the
        # kernel but the provider ABCs live in sibling modules that are all
        # imported by container.py.  Lazy imports keep the cycle-free invariant.
        provider = self._providers.get(key)
        if provider is None:
            raise ProviderRegistryError(
                f"No provider registered for '{key}'. "
                f"Call register_{key}() in build_container() before resolving."
            )
        if not isinstance(provider, expected_type):
            raise ProviderRegistryError(
                f"Provider registered for '{key}' is {type(provider).__name__!r}, "
                f"expected {expected_type.__name__!r}."
            )
        return provider
