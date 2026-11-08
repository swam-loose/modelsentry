from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.auth import ApiKeyCreate, BootstrapAdminCreate, UserCreate


def test_identity_schemas_normalize_email_and_names() -> None:
    bootstrap = BootstrapAdminCreate(
        email=" Admin@Example.COM ",
        display_name=" Administrator ",
    )
    user = UserCreate(
        email=" Reviewer@Example.COM ",
        display_name=" Release Reviewer ",
        role="reviewer",
    )

    assert bootstrap.email == "admin@example.com"
    assert bootstrap.display_name == "Administrator"
    assert user.email == "reviewer@example.com"
    assert user.role == "reviewer"


@pytest.mark.parametrize(
    "email",
    ["missing-at.example.com", "missing-domain@", "spaces @example.com"],
)
def test_identity_schemas_reject_invalid_email(email: str) -> None:
    with pytest.raises(ValidationError):
        UserCreate(email=email, display_name="User", role="viewer")


def test_user_schema_rejects_unknown_role_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "email": "user@example.com",
                "display_name": "User",
                "role": "owner",
            }
        )
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "email": "user@example.com",
                "display_name": "User",
                "role": "viewer",
                "password": "must-not-be-accepted",
            }
        )


def test_api_key_schema_normalizes_naive_expiration_to_utc() -> None:
    expires_at = datetime.now() + timedelta(days=1)

    payload = ApiKeyCreate(label=" Automation ", expires_at=expires_at)

    assert payload.label == "Automation"
    assert payload.expires_at is not None
    assert payload.expires_at.tzinfo == UTC
