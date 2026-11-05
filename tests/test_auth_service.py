from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.auth import ApiKeyCreate, BootstrapAdminCreate, UserCreate
from app.services.auth import (
    AuthConflictError,
    AuthenticationError,
    AuthNotFoundError,
    AuthService,
)


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        api_key_pepper=SecretStr("unit-test-pepper"),
        bootstrap_token=SecretStr("unit-test-bootstrap-token"),
    )


def bootstrap(service: AuthService) -> tuple[object, object]:
    return service.bootstrap_admin(
        BootstrapAdminCreate(
            email="admin@example.com",
            display_name="Administrator",
        ),
        "unit-test-bootstrap-token",
    )


def test_bootstrap_returns_one_time_key_and_persists_only_digest(
    db_session: Session,
) -> None:
    service = AuthService(db_session, make_settings())

    user, credential = bootstrap(service)

    assert user.role == "admin"
    assert credential.raw_key.startswith("msk_")
    assert credential.api_key.key_hash != credential.raw_key
    assert credential.api_key.key_hash == service.hash_api_key(
        credential.raw_key,
        service.settings.api_key_pepper,
    )


def test_bootstrap_rejects_wrong_token_and_reuse(db_session: Session) -> None:
    service = AuthService(db_session, make_settings())
    payload = BootstrapAdminCreate(
        email="admin@example.com",
        display_name="Administrator",
    )

    with pytest.raises(AuthenticationError):
        service.bootstrap_admin(payload, "wrong-token")
    bootstrap(service)
    with pytest.raises(AuthConflictError):
        service.bootstrap_admin(payload, "unit-test-bootstrap-token")


def test_user_registration_rejects_duplicate_email(db_session: Session) -> None:
    service = AuthService(db_session, make_settings())
    payload = UserCreate(
        email="viewer@example.com",
        display_name="Viewer",
        role="viewer",
    )

    service.create_user(payload)

    with pytest.raises(AuthConflictError):
        service.create_user(payload)


def test_issue_authenticate_and_revoke_api_key(db_session: Session) -> None:
    service = AuthService(db_session, make_settings())
    user = service.create_user(
        UserCreate(
            email="operator@example.com",
            display_name="Operator",
            role="operator",
        )
    )
    credential = service.issue_api_key(
        user.id,
        ApiKeyCreate(
            label="Automation",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        ),
    )

    authenticated = service.authenticate(credential.raw_key)

    assert authenticated.id == credential.api_key.id
    assert authenticated.last_used_at is not None
    service.revoke_api_key(authenticated.id)
    with pytest.raises(AuthenticationError):
        service.authenticate(credential.raw_key)
    with pytest.raises(AuthConflictError):
        service.revoke_api_key(authenticated.id)


def test_expired_and_inactive_credentials_are_rejected(db_session: Session) -> None:
    service = AuthService(db_session, make_settings())
    user = service.create_user(
        UserCreate(
            email="reviewer@example.com",
            display_name="Reviewer",
            role="reviewer",
        )
    )
    credential = service.issue_api_key(
        user.id,
        ApiKeyCreate(label="Review key"),
    )
    credential.api_key.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(AuthenticationError):
        service.authenticate(credential.raw_key)

    credential.api_key.expires_at = None
    user.is_active = False
    db_session.commit()
    with pytest.raises(AuthenticationError):
        service.authenticate(credential.raw_key)


def test_service_rejects_past_expiration_and_missing_resources(
    db_session: Session,
) -> None:
    service = AuthService(db_session, make_settings())
    user = service.create_user(
        UserCreate(
            email="viewer@example.com",
            display_name="Viewer",
            role="viewer",
        )
    )

    with pytest.raises(AuthConflictError):
        service.issue_api_key(
            user.id,
            ApiKeyCreate(
                label="Expired",
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            ),
        )
    with pytest.raises(AuthNotFoundError):
        service.get_user(uuid4())
    with pytest.raises(AuthNotFoundError):
        service.revoke_api_key(uuid4())
