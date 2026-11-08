from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.auth import ApiKey
from app.repositories.auth import AuthRepository
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
    assert user.bootstrap_slot == 1
    assert credential.raw_key.startswith("msk_")
    assert credential.api_key.key_hash != credential.raw_key
    assert credential.api_key.key_hash == service.hash_api_key(
        credential.raw_key,
        service.settings.api_key_pepper,
    )
    assert credential.raw_key not in repr(credential)


def test_bootstrap_rolls_back_user_when_key_persistence_fails(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AuthService(db_session, make_settings())
    with monkeypatch.context() as patch:
        patch.setattr(service, "hash_api_key", lambda *_: None)
        with pytest.raises(AuthConflictError):
            bootstrap(service)

    assert service.repository.count_users() == 0
    assert db_session.scalar(select(func.count(ApiKey.id))) == 0
    user, credential = bootstrap(service)
    assert user.is_active is True
    assert service.authenticate(credential.raw_key).user_id == user.id


def test_concurrent_bootstrap_has_only_one_winner(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = db_session.get_bind()
    barrier = Barrier(2)
    original_count = AuthRepository.count_users

    def synchronized_count(repository: AuthRepository) -> int:
        count = original_count(repository)
        barrier.wait(timeout=10)
        return count

    def attempt(index: int) -> str:
        with Session(engine) as session:
            service = AuthService(session, make_settings())
            try:
                service.bootstrap_admin(
                    BootstrapAdminCreate(
                        email=f"admin-{index}@example.com", display_name="Administrator"
                    ),
                    "unit-test-bootstrap-token",
                )
            except AuthConflictError:
                return "conflict"
            return "created"

    with monkeypatch.context() as patch:
        patch.setattr(AuthRepository, "count_users", synchronized_count)
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(attempt, (1, 2)))

    assert sorted(outcomes) == ["conflict", "created"]
    assert original_count(service_repository := AuthRepository(db_session)) == 1
    assert service_repository.session.scalar(select(func.count(ApiKey.id))) == 1


def test_inactive_user_cannot_receive_new_keys(db_session: Session) -> None:
    service = AuthService(db_session, make_settings())
    user = service.create_user(
        UserCreate(email="inactive@example.com", display_name="Inactive", role="viewer")
    )
    user.is_active = False
    db_session.commit()

    with pytest.raises(AuthConflictError, match="inactive user"):
        service.issue_api_key(user.id, ApiKeyCreate(label="Denied"))


def test_bootstrap_token_rejects_unicode_without_server_error(
    db_session: Session,
) -> None:
    service = AuthService(db_session, make_settings())
    with pytest.raises(AuthenticationError):
        service.bootstrap_admin(
            BootstrapAdminCreate(email="admin@example.com", display_name="Admin"),
            "not-the-token-\N{SNOWMAN}",
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
