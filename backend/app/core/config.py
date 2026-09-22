"""Application settings, loaded from environment variables / a .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # General
    environment: str = "development"
    project_name: str = "Gen-QA"

    # CORS: comma-separated list of allowed frontend origins
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    # Database
    database_url: str = "postgresql+asyncpg://genqa:genqa@localhost:5432/genqa"

    # Redis (not used by Sprint 1 features yet, but wired for future sprints)
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
