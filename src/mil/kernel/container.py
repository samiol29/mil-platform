"""
Dependency injection container for the MIL Platform.

The ``Container`` class is a lightweight service registry.  It supports
singleton and transient lifetimes and is the single point where concrete
provider implementations are bound to their abstract interfaces.

The platform has no compile-time dependency on any concrete implementation.
All providers (OCR, extraction, inference, storage, LOS adapter) are
registered here at application startup, after reading the deployment
configuration.  Bounded context code resolves them via
``container.resolve(InterfaceType)`` rather than importing concrete classes.

Usage::

    from mil.kernel.config import get_settings
    from mil.kernel.container import build_container

    container = build_container(get_settings())
    emitter = container.resolve(MetricEmitter)

Dependency rule: this module imports from ``mil.kernel.errors``,
``mil.kernel.config``, and ``mil.kernel.observability`` only.
No bounded context code should be imported here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable

from mil.kernel.config import Settings
from mil.kernel.errors import DependencyNotRegisteredError
from mil.kernel.event_bus import EventBus, InProcessEventBus
from mil.kernel.job_queue import InProcessJobQueue, JobQueue
from mil.kernel.metrics import InMemoryMetricEmitter
from mil.kernel.observability import MetricEmitter
from mil.kernel.providers.extraction import ExtractionProvider
from mil.kernel.providers.inference import InferenceProvider
from mil.kernel.providers.ocr import OCRProvider
from mil.kernel.providers.policy import PolicyProvider
from mil.kernel.providers.registry import ProviderRegistry
from mil.kernel.providers.storage import StorageProvider

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Internal binding record
# ---------------------------------------------------------------------------


class _Binding:
    """
    Internal record for a single registered dependency.

    Tracks whether the binding is singleton (instantiated once) or transient
    (factory called on each ``resolve``).  Singletons cache their instance
    after the first call to ``resolve``.
    """

    __slots__ = ("_factory", "_instance", "_resolved", "_singleton")

    def __init__(self, factory: Callable[[], Any], singleton: bool) -> None:
        self._factory = factory
        self._singleton = singleton
        self._instance: Any = None
        self._resolved = False

    def resolve(self) -> Any:
        if self._singleton:
            if not self._resolved:
                self._instance = self._factory()
                self._resolved = True
            return self._instance
        return self._factory()


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


class Container:
    """
    Lightweight dependency injection container.

    Bindings are registered by interface type and resolved on demand.  The
    container is assembled once at application startup by ``build_container``
    and then treated as immutable for the lifetime of the process.

    Binding lifetimes:

    - **Singleton** (``register_singleton``, ``register_instance``): the factory
      is called at most once; subsequent ``resolve`` calls return the cached
      instance.  Use for stateful infrastructure objects (database sessions,
      provider clients).

    - **Transient** (``register_transient``): the factory is called on every
      ``resolve``.  Use for lightweight, stateless service objects.
    """

    def __init__(self) -> None:
        self._bindings: dict[type[Any], _Binding] = {}

    # ---- Registration methods ----------------------------------------------

    def register_singleton(self, interface: type[T], factory: Callable[[], T]) -> None:
        """
        Register a singleton binding.

        The ``factory`` is called the first time ``resolve(interface)`` is
        called; the result is cached and returned on all subsequent calls.
        """
        self._bindings[interface] = _Binding(factory, singleton=True)

    def register_instance(self, interface: type[T], instance: T) -> None:
        """
        Register a pre-constructed instance as a singleton.

        Equivalent to ``register_singleton`` with a factory that returns the
        supplied ``instance``.
        """
        binding = _Binding(lambda: instance, singleton=True)
        binding._instance = instance
        binding._resolved = True
        self._bindings[interface] = binding

    def register_transient(self, interface: type[T], factory: Callable[[], T]) -> None:
        """
        Register a transient binding.

        The ``factory`` is called on every ``resolve(interface)`` call.
        """
        self._bindings[interface] = _Binding(factory, singleton=False)

    # ---- Resolution --------------------------------------------------------

    def resolve(self, interface: type[T]) -> T:
        """
        Resolve a registered dependency.

        Raises:
            DependencyNotRegisteredError: If no binding exists for ``interface``.
        """
        if interface not in self._bindings:
            raise DependencyNotRegisteredError(interface)
        return cast("T", self._bindings[interface].resolve())

    def is_registered(self, interface: type[Any]) -> bool:
        """Return ``True`` if a binding exists for ``interface``."""
        return interface in self._bindings

    def registered_interfaces(self) -> list[type[Any]]:
        """Return all currently registered interface types."""
        return list(self._bindings.keys())


# ---------------------------------------------------------------------------
# Application container factory
# ---------------------------------------------------------------------------


class ProductionReadinessError(RuntimeError):
    """
    Raised when a non-development process is assembled with a configuration
    that cannot safely serve production traffic.

    Backend Freeze Patch v1.0 makes these failures explicit at startup rather
    than allowing a process to run with development-only wiring (mock
    providers, ephemeral local storage, or the single-process in-memory
    message queue/bus) in a staging or production environment.
    """


# Class names that are only ever valid in development. A staging/production
# process that has any of these registered is misconfigured and must not start.
_DEVELOPMENT_ONLY_PROVIDERS: frozenset[str] = frozenset(
    {
        "MockOCRProvider",
        "MockExtractionProvider",
        "MockInferenceProvider",
        "MockPolicyProvider",
        "MockLOSAdapter",
        "LocalStorageProvider",
    }
)


def build_container(settings: Settings) -> Container:
    """
    Assemble and return the platform dependency injection container.

    This function is called once at application startup (in the FastAPI
    ``lifespan`` handler and in the worker bootstrap).

    Provider selection is governed by ``settings.mil_env``:

    - **development** — mock providers and the filesystem-backed
      ``LocalStorageProvider`` are registered for zero-configuration local use.
    - **staging / production** — mock and local development providers are
      forbidden. Real cloud-backed implementations must be wired in
      ``_register_production_providers``; none ship in this freeze, so a
      non-development process fails fast here (missing required providers, or
      a rejected development provider) rather than silently serving traffic
      with mock intelligence (Backend Freeze Patch v1.0, fixes 2 & 3).

    Bounded context code resolves providers through ``ProviderRegistry``
    rather than importing concrete classes::

        registry = container.resolve(ProviderRegistry)
        ocr = registry.get_ocr()

    Raises:
        ProviderRegistryError: If a required provider is missing.
        ProductionReadinessError: If a non-development process is wired with a
            development-only provider, or with the in-process message queue/bus
            that cannot deliver work across the platform's separate worker
            processes.
    """
    container = Container()

    # Platform settings — always available.
    container.register_instance(Settings, settings)

    # Metric emitter — in-process counters/histograms by default (Sprint 8:
    # exposed via GET /v1/metrics). Production deployments that need
    # cross-process aggregation register a different MetricEmitter here.
    container.register_instance(MetricEmitter, InMemoryMetricEmitter())  # type: ignore[type-abstract]

    # Event bus — in-process for development; broker-backed in production.
    container.register_singleton(EventBus, InProcessEventBus)  # type: ignore[type-abstract]

    # Job queue — in-process for development; broker-backed in production.
    container.register_singleton(JobQueue, InProcessJobQueue)

    # Provider registry — selected by environment.
    registry = _build_provider_registry(settings)
    if not settings.is_development():
        _reject_development_providers(registry)
    registry.validate()
    container.register_instance(ProviderRegistry, registry)

    # Individual provider bindings — resolved through the registry so
    # bounded contexts can use either resolution path.
    container.register_singleton(
        OCRProvider,  # type: ignore[type-abstract]
        lambda: container.resolve(ProviderRegistry).get_ocr(),
    )
    container.register_singleton(
        ExtractionProvider,  # type: ignore[type-abstract]
        lambda: container.resolve(ProviderRegistry).get_extraction(),
    )
    container.register_singleton(
        InferenceProvider,  # type: ignore[type-abstract]
        lambda: container.resolve(ProviderRegistry).get_inference(),
    )
    container.register_singleton(
        PolicyProvider,  # type: ignore[type-abstract]
        lambda: container.resolve(ProviderRegistry).get_policy(),
    )
    container.register_singleton(
        StorageProvider,  # type: ignore[type-abstract]
        lambda: container.resolve(ProviderRegistry).get_storage(),
    )

    # Reject the development-only in-process message queue/bus outside
    # development. The platform's supported non-development topology is
    # multi-process (API + worker processes); the in-memory JobQueue/EventBus
    # cannot deliver work across processes, so a staging/production process
    # wired with them is unsupported and must not start (ADR-007/008; the
    # broker-backed implementation is not part of this freeze).
    if not settings.is_development():
        _reject_in_process_messaging(container)

    return container


def _build_provider_registry(settings: Settings) -> ProviderRegistry:
    """
    Construct the ``ProviderRegistry`` for the active environment.

    Development registers mock/local providers. Staging and production must
    wire real providers via ``_register_production_providers``. The registry is
    returned unvalidated; ``build_container`` validates it (and, outside
    development, rejects any development-only provider) so the failure path is
    a single, explicit place.

    Separated from ``build_container`` so tests can obtain a registry directly.
    """
    registry = ProviderRegistry()
    if settings.is_development():
        _register_development_providers(registry)
    else:
        _register_production_providers(registry, settings)
    return registry


def _register_development_providers(registry: ProviderRegistry) -> None:
    """Register the mock/local development providers (development only)."""
    import pathlib
    import tempfile

    from providers.extraction.mock_extraction import MockExtractionProvider
    from providers.inference.mock_inference import MockInferenceProvider
    from providers.ocr.mock_ocr import MockOCRProvider
    from providers.policy.mock_policy import MockPolicyProvider
    from providers.storage.local_storage import LocalStorageProvider

    local_storage_path = pathlib.Path(tempfile.gettempdir()) / "mil-local-storage"

    registry.register_ocr(MockOCRProvider())
    registry.register_extraction(MockExtractionProvider())
    registry.register_inference(MockInferenceProvider())
    registry.register_policy(MockPolicyProvider())
    registry.register_storage(LocalStorageProvider(base_path=local_storage_path))
    # LOSAdapter is optional — register only when an integration is configured.


def _register_production_providers(registry: ProviderRegistry, settings: Settings) -> None:
    """
    Register real, cloud-backed providers for staging/production.

    No production provider implementations ship in this freeze. This function
    is the single, documented seam where they are wired; until they exist it
    registers nothing, so ``registry.validate()`` in ``build_container`` fails
    fast with a clear "required providers not registered" error rather than a
    process starting with mock intelligence. Mock/local providers MUST NOT be
    registered here (see ``_reject_development_providers``).
    """
    # Intentionally empty — see docstring. Real providers are wired here.


def _reject_development_providers(registry: ProviderRegistry) -> None:
    """
    Fail fast if any development-only provider is registered.

    Defence-in-depth for non-development environments: even if a future change
    wired a mock or ``LocalStorageProvider`` into the production path, startup
    is refused (Backend Freeze Patch v1.0, fix 2).
    """
    offending = {
        key: name
        for key, name in registry.registered_providers().items()
        if name in _DEVELOPMENT_ONLY_PROVIDERS
    }
    if offending:
        detail = ", ".join(f"{key}={name}" for key, name in sorted(offending.items()))
        raise ProductionReadinessError(
            "Development-only providers are not permitted outside development: "
            f"{detail}. Register production-grade providers in "
            "_register_production_providers()."
        )


def _reject_in_process_messaging(container: Container) -> None:
    """
    Fail fast if the in-process ``JobQueue``/``EventBus`` are registered outside
    development.

    These deliver only within a single process; the platform's supported
    non-development deployment runs the API and workers as separate processes,
    so in-memory messaging cannot coordinate them (ADR-007/008). A broker-backed
    implementation is out of scope for this freeze — the honest behaviour is to
    refuse to start rather than appear to work (Backend Freeze Patch v1.0, fix 3).
    """
    job_queue = container.resolve(JobQueue)
    event_bus = container.resolve(EventBus)  # type: ignore[type-abstract]
    if isinstance(job_queue, InProcessJobQueue) or isinstance(event_bus, InProcessEventBus):
        raise ProductionReadinessError(
            "The in-process JobQueue/EventBus cannot deliver work across the "
            "platform's separate worker processes and must not be used outside "
            "development. Register a broker-backed JobQueue and EventBus for "
            "staging/production (not part of Backend Freeze Patch v1.0)."
        )
