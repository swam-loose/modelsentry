from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_API_KEY_PEPPER = "development-only-change-me"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "ModelSentry API"
    app_version: str = "0.1.0"
    environment: Literal["development", "testing", "production"] = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./modelsentry.db"
    api_key_pepper: SecretStr = SecretStr(DEFAULT_API_KEY_PEPPER)
    bootstrap_token: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MODELSENTRY_",
        extra="ignore",
    )

    @model_validator(mode="after")
    def require_production_api_key_pepper(self) -> "Settings":
        """Reject the documented development pepper in production."""

        if (
            self.environment == "production"
            and self.api_key_pepper.get_secret_value() == DEFAULT_API_KEY_PEPPER
        ):
            raise ValueError(
                "MODELSENTRY_API_KEY_PEPPER must be changed in production."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
