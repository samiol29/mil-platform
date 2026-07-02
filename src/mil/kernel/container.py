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


def build_container(settings: Settings) -> Container:
    """
    Assemble and return the platform dependency injection container.

    This function is called once at application startup (in the FastAPI
    ``lifespan`` handler).

    Provider implementations registered here are the development defaults.
    Production deployments replace these with cloud-backed implementations
    by updating the relevant ``registry.register_*`` calls.

    Bounded context code resolves providers through ``ProviderRegistry``
    rather than importing concrete classes::

        registry = container.resolve(ProviderRegistry)
        ocr = registry.get_ocr()
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

    # Provider registry — build with development implementations.
    # Replace individual register_* calls to switch to cloud providers.
    registry = _build_provider_registry(settings)
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

    return container


def _build_provider_registry(settings: Settings) -> ProviderRegistry:
    """
    Construct and validate the ProviderRegistry with development providers.

    Separated from ``build_container`` so that tests can call this function
    directly to obtain a registry without a full container assembly.
    """
    import pathlib
    import tempfile

    from providers.extraction.mock_extraction import MockExtractionProvider
    from providers.inference.mock_inference import MockInferenceProvider
    from providers.ocr.mock_ocr import MockOCRProvider
    from providers.policy.mock_policy import MockPolicyProvider
    from providers.storage.local_storage import LocalStorageProvider

    local_storage_path = pathlib.Path(tempfile.gettempdir()) / "mil-local-storage"

    registry = ProviderRegistry()
    registry.register_ocr(MockOCRProvider())
    registry.register_extraction(MockExtractionProvider())
    registry.register_inference(MockInferenceProvider())
    registry.register_policy(MockPolicyProvider())
    registry.register_storage(LocalStorageProvider(base_path=local_storage_path))
    # LOSAdapter is optional — register only when an integration is configured.

    registry.validate()
    return registry
