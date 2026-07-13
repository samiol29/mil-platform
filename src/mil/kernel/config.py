"""
Platform-wide settings schema for the MIL Platform.

All configuration values are read from environment variables.  The canonical
variable names and their default values are documented in ``.env.example`` at
the repository root.

Usage::

    from mil.kernel.config import get_settings

    settings = get_settings()
    db_url = settings.database_async_url

``get_settings()`` is cached with ``lru_cache`` so environment variables are
read exactly once per process.  In tests, call ``get_settings.cache_clear()``
and use ``monkeypatch.setenv`` to isolate settings state between test cases.

Pydantic-settings resolves field values in priority order (highest to lowest):
  1. Explicit keyword arguments (e.g. ``Settings(mil_env="staging")``)
  2. Environment variables (case-insensitive by default)
  3. ``.env`` file at the repository root (if present)
  4. Field default values

Dependency rule: this module imports only from the Python standard library and
from pydantic / pydantic-settings.  It MUST NOT import from other kernel
modules to avoid circular imports.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Typed settings schema.

    Field names are lowercase snake_case versions of the corresponding
    environment variable names.  Pydantic-settings maps them case-insensitively:
    ``mil_env`` ← ``MIL_ENV``, ``postgres_host`` ← ``POSTGRES_HOST``, etc.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application -------------------------------------------------------
    mil_env: Literal["development", "staging", "production"] = "development"
    mil_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    mil_host: str = "0.0.0.0"
    mil_port: int = 8000
    mil_secret_key: SecretStr = Field(default=SecretStr("changeme-replace-in-all-environments"))
    mil_region: str | None = None
    # Dedicated HMAC signing key for Customer Portal session tokens (spec
    # 005-enterprise-platform §12, Wave 4) — deliberately distinct from
    # mil_secret_key so a portal-token verification bug can never be
    # confused with internal-staff token verification (a genuinely separate
    # trust boundary, not a shared-secret convenience).
    mil_portal_secret_key: SecretStr = Field(
        default=SecretStr("changeme-replace-in-all-environments")
    )

    # ---- PostgreSQL --------------------------------------------------------
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "mil"
    postgres_user: str = "mil"
    postgres_password: SecretStr = Field(default=SecretStr("changeme"))

    # ---- Object Storage (MinIO / S3-compatible) ----------------------------
    storage_endpoint: str = "http://localhost:9000"
    storage_access_key: str = "minioadmin"
    storage_secret_key: SecretStr = Field(default=SecretStr("minioadmin"))
    storage_bucket: str = "mil-documents"
    storage_region: str = "us-east-1"

    # ---- Message Broker (Redis) --------------------------------------------
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: SecretStr | None = None

    # ---- Inference (AI Copilot / Findings) ---------------------------------
    # Which InferenceProvider implementation the container wires (ADR-011 §3,
    # provider-agnostic inference). "gemini" is the only implemented provider
    # today; add "claude" / "openai" / "azure_openai" / "vllm" / "ollama" here
    # (and a branch in ``mil.kernel.container._build_inference_provider``) as
    # each provider class lands — business logic never changes.
    inference_provider: str = "gemini"

    # Google Gemini AI Studio. The API key is a secret read from GEMINI_API_KEY
    # and injected into ``GeminiInferenceProvider`` by the container — it is
    # never hardcoded and never sent in a URL (see the provider's auth header).
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    gemini_max_output_tokens: int = Field(default=1024, gt=0)
    gemini_timeout_seconds: float = Field(default=30.0, gt=0)
    gemini_max_retries: int = Field(default=4, ge=0)

    # ---- Document Intelligence (OCR / Extraction) --------------------------
    # Which OCRProvider / ExtractionProvider implementation the container
    # wires. "gemini" (native multimodal document understanding — no
    # traditional OCR engine) is the only implemented value today. Same DI
    # seam as inference: add a branch to ``_build_ocr_provider`` /
    # ``_build_extraction_provider`` for a future engine — no business-logic
    # change (ARCHITECTURE.md §5).
    ocr_provider: str = "gemini"
    extraction_provider: str = "gemini"

    # Gemini can use a lighter/cheaper model per stage than the Copilot
    # inference model; both default to the same flash model as a sane default.
    # The API key, base URL, timeout, and retry budget are shared with
    # inference (``gemini_api_key`` etc. above) — one secret, one retry
    # policy, three call sites.
    gemini_ocr_model: str = "gemini-2.5-flash"
    gemini_extraction_model: str = "gemini-2.5-flash"

    # ---- Observability (OpenTelemetry) -------------------------------------
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "mil-api"

    # ---- Worker ------------------------------------------------------------
    worker_concurrency: int = 4
    worker_job_timeout: int = 120

    # ---- Upload limits -----------------------------------------------------
    # Maximum accepted size, in bytes, for a single document upload. Requests
    # whose body exceeds this are rejected with HTTP 413 before the whole file
    # is buffered in memory (Backend Freeze Patch v1.0 — upload safety).
    mil_max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0)

    # ---- Derived URLs (read-only properties) -------------------------------

    @property
    def database_async_url(self) -> str:
        """SQLAlchemy async URL for asyncpg (used by the FastAPI application)."""
        pw = self.postgres_password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{pw}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_sync_url(self) -> str:
        """SQLAlchemy sync URL for psycopg2 (used by Alembic migration runner)."""
        pw = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{pw}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def broker_url(self) -> str:
        """Redis URL for the message broker and job queue."""
        if self.redis_password is not None:
            pw = self.redis_password.get_secret_value()
            auth = f":{pw}@"
        else:
            auth = ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ---- Convenience predicates --------------------------------------------

    def is_production(self) -> bool:
        """Return True when running in the production environment."""
        return self.mil_env == "production"

    def is_development(self) -> bool:
        """Return True when running in a local development environment."""
        return self.mil_env == "development"

    # ---- Validators --------------------------------------------------------

    @model_validator(mode="after")
    def _reject_insecure_defaults_in_production(self) -> Settings:
        """
        Guard against deploying with placeholder secret values in production.

        This is a defence-in-depth check.  Secret rotation and key management
        are handled by dedicated infrastructure (Engineering Constitution,
        Principle V); this validator catches the most common misconfiguration.
        """
        if not self.is_production():
            return self

        # Substring match, not an exact-value set (spec 005-enterprise-
        # platform §16/§14, Wave 4 — a real gap found during this module's
        # audit): the checked-in `.env.example`'s own placeholder,
        # "changeme-use-openssl-rand-hex-32-in-production", was NOT caught
        # by the previous exact-match `_insecure_markers` set — a
        # deployment that forgot to override MIL_SECRET_KEY but did set
        # MIL_ENV=production would have silently passed this check. Any
        # value containing "changeme" is now rejected, closing that gap.
        def _is_placeholder(value: str) -> bool:
            return "changeme" in value.lower()

        if _is_placeholder(self.mil_secret_key.get_secret_value()):
            print(
                "FATAL: MIL_SECRET_KEY is set to a development placeholder. "
                "Production deployments must use a cryptographically random secret key.",
                file=sys.stderr,
            )
            raise ValueError("MIL_SECRET_KEY must not be a placeholder value in production")

        if _is_placeholder(self.postgres_password.get_secret_value()):
            raise ValueError("POSTGRES_PASSWORD must not be a placeholder value in production")

        if _is_placeholder(self.mil_portal_secret_key.get_secret_value()):
            raise ValueError("MIL_PORTAL_SECRET_KEY must not be a placeholder value in production")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached platform settings instance.

    The settings object is constructed once and reused for the process lifetime.
    Call ``get_settings.cache_clear()`` in tests to force re-initialisation from
    the current environment state.
    """
    return Settings()
