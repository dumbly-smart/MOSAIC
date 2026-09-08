"""Environment-backed API configuration."""

from functools import lru_cache

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets are read only by the API process."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MOSAIC_", extra="ignore")

    app_name: str = "MOSAIC Verification API"
    environment: str = "development"
    database_url: str | None = None
    supabase_url: HttpUrl | None = None
    supabase_publishable_key: str | None = None
    supabase_secret_key: str | None = None
    storage_bucket: str = "mosaic-documents"
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
