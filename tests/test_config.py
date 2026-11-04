from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_API_KEY_PEPPER, Settings, get_settings


def test_default_settings() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "ModelSentry API"
    assert settings.app_version == "0.1.0"
    assert settings.environment == "development"
    assert settings.api_prefix == "/api/v1"
    assert settings.database_url == "sqlite:///./modelsentry.db"
    assert settings.api_key_pepper.get_secret_value() == DEFAULT_API_KEY_PEPPER
    assert settings.bootstrap_token is None


def test_environment_overrides_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        "MODELSENTRY_ENVIRONMENT=testing\nMODELSENTRY_APP_NAME=From dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MODELSENTRY_ENVIRONMENT", "production")
    monkeypatch.setenv("MODELSENTRY_API_KEY_PEPPER", "production-secret-pepper")

    settings = Settings()

    assert settings.environment == "production"
    assert settings.app_name == "From dotenv"


def test_production_rejects_development_api_key_pepper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODELSENTRY_ENVIRONMENT", "production")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_invalid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODELSENTRY_ENVIRONMENT", "invalid")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_are_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    initial_settings = get_settings()
    monkeypatch.setenv("MODELSENTRY_APP_NAME", "Updated service")

    assert get_settings() is initial_settings

    get_settings.cache_clear()

    assert get_settings().app_name == "Updated service"
