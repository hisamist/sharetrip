"""Unit tests for the Settings config module."""

from sharetrip.config import Settings, get_settings


class TestSettings:
    def test_default_database_url(self):
        assert Settings().database_url == "sqlite:///./sharetrip.db"

    def test_default_redis_url(self):
        assert Settings().redis_url == "redis://localhost:6379/0"

    def test_default_frankfurter_base_url(self):
        assert Settings().frankfurter_base_url == "https://api.frankfurter.app"

    def test_default_currency_cache_ttl(self):
        assert Settings().currency_cache_ttl == 86_400

    def test_default_repo_cache_ttl(self):
        assert Settings().repo_cache_ttl == 300

    def test_default_jwt_expire_minutes(self):
        assert Settings().jwt_expire_minutes == 60 * 24

    def test_default_app_env(self):
        assert Settings().app_env == "development"

    def test_database_url_overridable_via_env(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/test")
        s = Settings()
        assert s.database_url == "postgresql://user:pass@localhost/test"

    def test_app_env_overridable_via_env(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        s = Settings()
        assert s.app_env == "production"

    def test_jwt_secret_key_overridable_via_env(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "my-custom-secret-key-for-testing-ok")
        s = Settings()
        assert s.jwt_secret_key == "my-custom-secret-key-for-testing-ok"


class TestGetSettings:
    def test_returns_settings_instance(self):
        assert isinstance(get_settings(), Settings)

    def test_is_singleton(self):
        assert get_settings() is get_settings()
