from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base de données
    database_url: str = "sqlite:///./sharetrip.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API de change
    frankfurter_base_url: str = "https://api.frankfurter.app"
    currency_cache_ttl: int = 86_400  # 24h en secondes

    # Cache Repository
    repo_cache_ttl: int = 300  # 5min en secondes

    # App
    app_env: str = "development"  # development | production

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Singleton — l'instance est créée une seule fois et réutilisée."""
    return Settings()
