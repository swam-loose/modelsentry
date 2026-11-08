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
    monkeypatch.setenv(
        "MODELSENTRY_API_KEY_PEPPER", "production-test-pepper-" + "x" * 32
    )

    settings = Settings()

    assert settings.environment == "production"
    assert settings.app_name == "From dotenv"


def test_production_rejects_development_api_key_pepper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODELSENTRY_ENVIRONMENT", "production")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("secret_name", ["api_key_pepper", "bootstrap_token"])
@pytest.mark.parametrize("value", ["", "   "])
def test_settings_reject_empty_secrets(secret_name: str, value: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{secret_name: value})


@pytest.mark.parametrize(
    "secret_name,value",
    [
        ("api_key_pepper", "short"),
        ("api_key_pepper", "replace-with-a-long-random-secret"),
        ("bootstrap_token", "short"),
        ("bootstrap_token", "replace-with-a-separate-one-time-secret"),
    ],
)
def test_production_rejects_weak_or_placeholder_secrets(
    secret_name: str, value: str
) -> None:
    settings = {
        "environment": "production",
        "api_key_pepper": "production-test-pepper-" + "x" * 32,
        secret_name: value,
    }
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **settings)


def test_production_requires_separate_bootstrap_and_hashing_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            api_key_pepper="same-test-secret-" + "x" * 32,
            bootstrap_token="same-test-secret-" + "x" * 32,
        )


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
