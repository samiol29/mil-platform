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

import redis

if TYPE_CHECKING:
    from collections.abc import Callable

from mil.kernel.config import Settings
from mil.kernel.errors import DependencyNotRegisteredError
from mil.kernel.event_bus import EventBus, InProcessEventBus
from mil.kernel.job_queue import InProcessJobQueue, JobQueue, RedisJobQueue
from mil.kernel.metrics import InMemoryMetricEmitter
from mil.kernel.observability import MetricEmitter
from mil.kernel.providers.extraction import ExtractionProvider
from mil.kernel.providers.inference import InferenceProvider
from mil.kernel.providers.ocr import OCRProvider
from mil.kernel.providers.policy import PolicyProvider
from mil.kernel.providers.registry import ProviderRegistry, ProviderRegistryError
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

    # Job queue — Redis-backed in every environment. The API process and every
    # worker process must observe the same queue state (ADR-007/ADR-008: the
    # plan's production topology is multi-process — API + worker processes +
    # broker); InProcessJobQueue cannot deliver work across that boundary and
    # is never wired here. See _build_job_queue().
    container.register_singleton(JobQueue, lambda: _build_job_queue(settings))

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


def _build_job_queue(settings: Settings) -> JobQueue:
    """
    Construct the platform ``JobQueue`` — ``RedisJobQueue`` in every
    environment.

    Same DI seam as the intelligence providers (``_build_inference_provider``
    etc.): the concrete implementation is selected here, and nothing above
    this function (``IntelligenceOrchestrator``, the worker processors,
    ``workers/bootstrap.py``) knows or cares that Redis is behind the
    interface. ``settings.broker_url`` is the existing Redis DSN, constructed
    from ``REDIS_HOST``/``REDIS_PORT``/``REDIS_DB``/``REDIS_PASSWORD``
    (``Settings.broker_url``, already used by the docker-compose-provisioned
    Redis instance documented as "the message broker backing the EventBus and
    JobQueue").

    The client is constructed lazily (``redis.Redis.from_url`` does not
    connect until the first command), so building the container never fails
    or blocks even if Redis is not reachable yet — the same fail-fast-at-use,
    not-at-construction behaviour as the other provider builders.

    ``socket_timeout`` must exceed the largest ``timeout`` any caller passes to
    ``JobQueue.dequeue()`` (a worker's polling loop uses
    ``_POLL_TIMEOUT_SECONDS = 5.0``), or redis-py's socket read timeout fires
    *before* Redis's own ``BLPOP`` timeout does, surfacing as an unhandled
    ``redis.exceptions.TimeoutError`` that crashes the worker process instead
    of ``dequeue`` returning ``None`` for an empty queue (this is a documented
    redis-py behaviour, not a bug in this platform's queue logic — verified by
    running a real worker process against it).
    """
    client = redis.Redis.from_url(settings.broker_url, decode_responses=True, socket_timeout=30.0)
    return RedisJobQueue(client)


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
        _register_development_providers(registry, settings)
    else:
        _register_production_providers(registry, settings)
    return registry


def _build_inference_provider(settings: Settings) -> InferenceProvider:
    """
    Construct the configured real ``InferenceProvider``.

    Selection is by ``settings.inference_provider`` — the single, DI-only seam
    that keeps inference provider-agnostic (ARCHITECTURE.md §5/§6, ADR-011 §3).
    Adding Claude / OpenAI / Azure OpenAI / vLLM / Ollama is: implement the
    ``InferenceProvider`` in ``src/providers/inference/`` and add a branch here.
    No business-logic module changes.

    Gemini is the only implemented provider today. Its API key is read from the
    environment via ``Settings`` (``GEMINI_API_KEY``) and injected here — the
    provider never reads the environment itself, and the key is never hardcoded.

    Raises:
        ProviderRegistryError: If the configured provider name is unknown, or a
            required secret (the Gemini API key) is missing — fail fast at
            startup rather than at first Copilot call.
    """
    name = settings.inference_provider.strip().lower()
    if name == "gemini":
        from providers.inference.gemini_inference import GeminiInferenceProvider

        if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
            raise ProviderRegistryError(
                "GEMINI_API_KEY is required when INFERENCE_PROVIDER='gemini'. "
                "Set it from your secret manager (see .env.example)."
            )
        return GeminiInferenceProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            base_url=settings.gemini_base_url,
            temperature=settings.gemini_temperature,
            max_output_tokens=settings.gemini_max_output_tokens,
            timeout_seconds=settings.gemini_timeout_seconds,
            max_retries=settings.gemini_max_retries,
        )
    raise ProviderRegistryError(
        f"Unknown inference_provider {settings.inference_provider!r}. Implement an "
        "InferenceProvider in src/providers/inference/ and add a branch to "
        "_build_inference_provider()."
    )


def _build_ocr_provider(settings: Settings) -> OCRProvider:
    """
    Construct the configured real ``OCRProvider``.

    Selection is by ``settings.ocr_provider`` — the same DI-only seam pattern
    as ``_build_inference_provider``. Gemini's native multimodal document
    understanding is the only implemented value today (there is no traditional
    OCR engine in this platform).

    Raises:
        ProviderRegistryError: If the configured provider name is unknown, or
            ``GEMINI_API_KEY`` is missing.
    """
    name = settings.ocr_provider.strip().lower()
    if name == "gemini":
        from providers.ocr.gemini_ocr import GeminiOCRProvider

        if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
            raise ProviderRegistryError(
                "GEMINI_API_KEY is required when OCR_PROVIDER='gemini'. "
                "Set it from your secret manager (see .env.example)."
            )
        return GeminiOCRProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_ocr_model,
            base_url=settings.gemini_base_url,
            timeout_seconds=settings.gemini_timeout_seconds,
            max_retries=settings.gemini_max_retries,
        )
    raise ProviderRegistryError(
        f"Unknown ocr_provider {settings.ocr_provider!r}. Implement an OCRProvider "
        "in src/providers/ocr/ and add a branch to _build_ocr_provider()."
    )


def _build_extraction_provider(settings: Settings) -> ExtractionProvider:
    """
    Construct the configured real ``ExtractionProvider``.

    Selection is by ``settings.extraction_provider`` — same DI-only seam as
    inference and OCR. Gemini structured-output extraction over already-OCR'd
    text is the only implemented value today.

    Raises:
        ProviderRegistryError: If the configured provider name is unknown, or
            ``GEMINI_API_KEY`` is missing.
    """
    name = settings.extraction_provider.strip().lower()
    if name == "gemini":
        from providers.extraction.gemini_extraction import GeminiExtractionProvider

        if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
            raise ProviderRegistryError(
                "GEMINI_API_KEY is required when EXTRACTION_PROVIDER='gemini'. "
                "Set it from your secret manager (see .env.example)."
            )
        return GeminiExtractionProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_extraction_model,
            base_url=settings.gemini_base_url,
            timeout_seconds=settings.gemini_timeout_seconds,
            max_retries=settings.gemini_max_retries,
        )
    raise ProviderRegistryError(
        f"Unknown extraction_provider {settings.extraction_provider!r}. Implement an "
        "ExtractionProvider in src/providers/extraction/ and add a branch to "
        "_build_extraction_provider()."
    )


def _register_development_providers(registry: ProviderRegistry, settings: Settings) -> None:
    """
    Register development providers.

    Policy and storage remain mock/local (zero-configuration local use, out of
    scope for the document intelligence change). OCR, Extraction, and
    Inference are now all real in every environment — Gemini native document
    understanding, Gemini structured extraction, and Gemini inference
    respectively — so local development exercises the same intelligence path
    as production. Local development therefore requires a valid
    ``GEMINI_API_KEY``; the ``_build_*_provider`` functions fail fast if it is
    absent.
    """
    import pathlib
    import tempfile

    from providers.policy.mock_policy import MockPolicyProvider
    from providers.storage.local_storage import LocalStorageProvider

    local_storage_path = pathlib.Path(tempfile.gettempdir()) / "mil-local-storage"

    registry.register_ocr(_build_ocr_provider(settings))
    registry.register_extraction(_build_extraction_provider(settings))
    registry.register_inference(_build_inference_provider(settings))
    registry.register_policy(MockPolicyProvider())
    registry.register_storage(LocalStorageProvider(base_path=local_storage_path))
    # LOSAdapter is optional — register only when an integration is configured.


def _register_production_providers(registry: ProviderRegistry, settings: Settings) -> None:
    """
    Register real, cloud-backed providers for staging/production.

    OCR, Extraction, and Inference are wired here via the ``_build_*_provider``
    functions (all Gemini today). Policy and storage are not part of this
    change, so ``registry.validate()`` in ``build_container`` still fails fast
    for them with a clear "required providers not registered" error rather
    than a process starting with missing intelligence. Mock/local providers
    MUST NOT be registered here (see ``_reject_development_providers``).
    """
    registry.register_ocr(_build_ocr_provider(settings))
    registry.register_extraction(_build_extraction_provider(settings))
    registry.register_inference(_build_inference_provider(settings))
    # Policy / storage: real implementations wired here as they land (out of
    # scope for the document intelligence change).


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
