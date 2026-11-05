from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.auth import AuthRepository
from app.schemas.auth import UserCreate


def test_auth_repository_persists_users_and_hashed_keys(
    db_session: Session,
) -> None:
    repository = AuthRepository(db_session)
    user = repository.create_user(
        UserCreate(
            email="operator@example.com",
            display_name="Operator",
            role="operator",
        )
    )
    api_key = repository.create_api_key(
        user.id,
        label="CI",
        key_prefix="msk_example",
        key_hash="a" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )

    assert repository.count_users() == 1
    assert repository.get_user(user.id) is user
    assert repository.get_user_by_email("OPERATOR@EXAMPLE.COM") is user
    assert repository.list_users() == [user]
    assert repository.get_api_key_by_hash("a" * 64) is api_key
    assert repository.list_api_keys(user.id) == [api_key]


def test_auth_repository_records_use_and_revocation(db_session: Session) -> None:
    repository = AuthRepository(db_session)
    user = repository.create_user(
        UserCreate(
            email="viewer@example.com",
            display_name="Viewer",
            role="viewer",
        )
    )
    api_key = repository.create_api_key(
        user.id,
        label="Read only",
        key_prefix="msk_viewer",
        key_hash="b" * 64,
        expires_at=None,
    )

    repository.record_use(api_key)
    repository.revoke(api_key)

    assert api_key.last_used_at is not None
    assert api_key.revoked_at is not None
