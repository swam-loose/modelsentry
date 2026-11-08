from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_API_KEY_PEPPER = "development-only-change-me"
SECRET_PLACEHOLDERS = {
    DEFAULT_API_KEY_PEPPER,
    "replace-with-a-long-random-secret",
    "replace-with-a-separate-one-time-secret",
}


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
        """Reject empty secrets and predictable production placeholders."""

        pepper = self.api_key_pepper.get_secret_value()
        if not pepper.strip():
            raise ValueError("MODELSENTRY_API_KEY_PEPPER must not be empty.")
        if self.bootstrap_token is not None:
            token = self.bootstrap_token.get_secret_value()
            if not token.strip():
                raise ValueError("MODELSENTRY_BOOTSTRAP_TOKEN must not be empty.")
        else:
            token = None
        if self.environment == "production":
            for name, value in (
                ("MODELSENTRY_API_KEY_PEPPER", pepper),
                ("MODELSENTRY_BOOTSTRAP_TOKEN", token),
            ):
                if value is not None and (
                    value in SECRET_PLACEHOLDERS or len(value) < 32
                ):
                    raise ValueError(
                        f"{name} must be a unique random secret of at least "
                        "32 characters in production."
                    )
            if token == pepper:
                raise ValueError("Bootstrap token and API-key pepper must differ.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
