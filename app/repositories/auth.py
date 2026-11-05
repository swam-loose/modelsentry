from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.auth import ApiKey, UserAccount
from app.schemas.auth import UserCreate


class AuthRepository:
    """Persist local identities and irreversible API-key digests."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def count_users(self) -> int:
        return self.session.scalar(select(func.count(UserAccount.id))) or 0

    def create_user(self, payload: UserCreate) -> UserAccount:
        user = UserAccount(**payload.model_dump())
        self.session.add(user)
        self._commit()
        self.session.refresh(user)
        return user

    def get_user(self, user_id: UUID) -> UserAccount | None:
        return self.session.get(UserAccount, user_id)

    def get_user_by_email(self, email: str) -> UserAccount | None:
        statement = select(UserAccount).where(UserAccount.email == email.lower())
        return self.session.scalar(statement)

    def list_users(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[UserAccount]:
        statement = (
            select(UserAccount)
            .order_by(UserAccount.created_at, UserAccount.id)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def create_api_key(
        self,
        user_id: UUID,
        *,
        label: str,
        key_prefix: str,
        key_hash: str,
        expires_at: datetime | None,
    ) -> ApiKey:
        api_key = ApiKey(
            user_id=user_id,
            label=label,
            key_prefix=key_prefix,
            key_hash=key_hash,
            expires_at=expires_at,
        )
        self.session.add(api_key)
        self._commit()
        self.session.refresh(api_key)
        return api_key

    def get_api_key(self, api_key_id: UUID) -> ApiKey | None:
        return self.session.get(ApiKey, api_key_id)

    def get_api_key_by_hash(self, key_hash: str) -> ApiKey | None:
        statement = (
            select(ApiKey)
            .where(ApiKey.key_hash == key_hash)
            .options(selectinload(ApiKey.user))
        )
        return self.session.scalar(statement)

    def list_api_keys(self, user_id: UUID) -> list[ApiKey]:
        statement = (
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at, ApiKey.id)
        )
        return list(self.session.scalars(statement))

    def record_use(self, api_key: ApiKey) -> ApiKey:
        api_key.last_used_at = datetime.now(UTC)
        self._commit()
        self.session.refresh(api_key)
        return api_key

    def revoke(self, api_key: ApiKey) -> ApiKey:
        api_key.revoked_at = datetime.now(UTC)
        self._commit()
        self.session.refresh(api_key)
        return api_key

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
