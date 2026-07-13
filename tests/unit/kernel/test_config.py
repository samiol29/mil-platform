"""Unit tests for mil.kernel.config — settings schema and URL properties."""

from __future__ import annotations

import pytest

from mil.kernel.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    """Clear the lru_cache before and after each test."""
    get_settings.cache_clear()
    yield  # type: ignore[misc]
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Settings construction and defaults
# ---------------------------------------------------------------------------


class TestSettingsDefaults:
    def test_default_env_is_development(self) -> None:
        s = Settings()
        assert s.mil_env == "development"

    def test_default_log_level_is_info(self) -> None:
        s = Settings()
        assert s.mil_log_level == "INFO"

    def test_default_host_and_port(self) -> None:
        s = Settings()
        assert s.mil_host == "0.0.0.0"
        assert s.mil_port == 8000

    def test_default_postgres_host(self) -> None:
        s = Settings()
        assert s.postgres_host == "localhost"
        assert s.postgres_port == 5432

    def test_default_redis_host(self) -> None:
        s = Settings()
        assert s.redis_host == "localhost"
        assert s.redis_port == 6379
        assert s.redis_db == 0

    def test_default_storage_bucket(self) -> None:
        s = Settings()
        assert s.storage_bucket == "mil-documents"

    def test_default_worker_concurrency(self) -> None:
        s = Settings()
        assert s.worker_concurrency == 4

    def test_mil_region_defaults_to_none(self) -> None:
        s = Settings()
        assert s.mil_region is None

    def test_redis_password_defaults_to_none(self) -> None:
        s = Settings()
        assert s.redis_password is None


# ---------------------------------------------------------------------------
# URL properties
# ---------------------------------------------------------------------------


class TestURLProperties:
    def test_database_async_url_uses_asyncpg_scheme(self) -> None:
        s = Settings(postgres_host="db.example.com", postgres_port=5432, postgres_db="mydb")
        assert s.database_async_url.startswith("postgresql+asyncpg://")

    def test_database_async_url_contains_host_and_db(self) -> None:
        s = Settings(postgres_host="db.example.com", postgres_db="mil_prod")
        assert "db.example.com" in s.database_async_url
        assert "mil_prod" in s.database_async_url

    def test_database_sync_url_uses_psycopg2_scheme(self) -> None:
        s = Settings()
        assert s.database_sync_url.startswith("postgresql+psycopg2://")

    def test_broker_url_no_password(self) -> None:
        s = Settings(redis_host="redis.local", redis_port=6380, redis_db=1)
        url = s.broker_url
        assert url.startswith("redis://")
        assert "redis.local:6380/1" in url
        assert "@" not in url

    def test_broker_url_with_password(self) -> None:
        s = Settings(redis_password="s3cr3t")
        url = s.broker_url
        assert "@" in url
        assert "s3cr3t" in url


# ---------------------------------------------------------------------------
# Environment predicates
# ---------------------------------------------------------------------------


class TestEnvironmentPredicates:
    def test_is_development_true_by_default(self) -> None:
        s = Settings()
        assert s.is_development() is True
        assert s.is_production() is False

    def test_is_production_true(self) -> None:
        s = Settings(
            mil_env="production",
            mil_secret_key="crypto-random-long-enough-secret-key",
            postgres_password="secure-db-password",
            mil_portal_secret_key="crypto-random-long-enough-portal-key",
        )
        assert s.is_production() is True
        assert s.is_development() is False

    def test_staging_is_neither(self) -> None:
        s = Settings(mil_env="staging")
        assert s.is_development() is False
        assert s.is_production() is False


# ---------------------------------------------------------------------------
# Production safety validator
# ---------------------------------------------------------------------------


class TestProductionSafetyValidator:
    def test_placeholder_secret_key_fails_in_production(self) -> None:
        with pytest.raises(ValueError, match="MIL_SECRET_KEY"):
            Settings(mil_env="production", postgres_password="secure-password")

    def test_placeholder_db_password_fails_in_production(self) -> None:
        with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
            Settings(
                mil_env="production",
                mil_secret_key="crypto-long-random-secret-key-value",
                postgres_password="changeme",
            )

    def test_placeholder_portal_secret_key_fails_in_production(self) -> None:
        with pytest.raises(ValueError, match="MIL_PORTAL_SECRET_KEY"):
            Settings(
                mil_env="production",
                mil_secret_key="crypto-long-random-secret-key-value",
                postgres_password="secure-db-password",
            )

    def test_valid_production_settings_accepted(self) -> None:
        s = Settings(
            mil_env="production",
            mil_secret_key="crypto-random-long-enough-secret-key",
            postgres_password="secure-db-password",
            mil_portal_secret_key="crypto-random-long-enough-portal-key",
        )
        assert s.is_production()

    def test_placeholder_secret_allowed_in_development(self) -> None:
        s = Settings(mil_env="development")
        assert s.is_development()


# ---------------------------------------------------------------------------
# get_settings cache
# ---------------------------------------------------------------------------


class TestGetSettings:
    def test_get_settings_returns_settings(self) -> None:
        s = get_settings()
        assert isinstance(s, Settings)

    def test_get_settings_cached(self) -> None:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_get_settings_cache_clear(self) -> None:
        s1 = get_settings()
        get_settings.cache_clear()
        s2 = get_settings()
        assert s1 is not s2
