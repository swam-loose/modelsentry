import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.auth import ApiKey, UserAccount
from app.repositories.auth import AuthRepository
from app.schemas.auth import (
    ApiKeyCreate,
    BootstrapAdminCreate,
    UserCreate,
)


class AuthConflictError(Exception):
    """Raised when identity state conflicts with the requested operation."""


class AuthNotFoundError(Exception):
    """Raised when a user or credential cannot be found."""


class AuthenticationError(Exception):
    """Raised when supplied credential material is not acceptable."""


@dataclass(frozen=True)
class IssuedCredential:
    """Credential metadata and the raw secret returned exactly once."""

    api_key: ApiKey
    raw_key: str


class AuthService:
    """Create, hash, authenticate, expire, and revoke local API keys."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.repository = AuthRepository(session)
        self.settings = settings or get_settings()

    @staticmethod
    def generate_api_key() -> str:
        return f"msk_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_api_key(raw_key: str, pepper: SecretStr) -> str:
        return hmac.new(
            pepper.get_secret_value().encode(),
            raw_key.encode(),
            sha256,
        ).hexdigest()

    def _issue_api_key(
        self,
        user: UserAccount,
        payload: ApiKeyCreate,
    ) -> IssuedCredential:
        if payload.expires_at is not None and payload.expires_at <= datetime.now(UTC):
            raise AuthConflictError("API-key expiration must be in the future.")
        raw_key = self.generate_api_key()
        api_key = self.repository.create_api_key(
            user.id,
            label=payload.label,
            key_prefix=raw_key[:12],
            key_hash=self.hash_api_key(raw_key, self.settings.api_key_pepper),
            expires_at=payload.expires_at,
        )
        return IssuedCredential(api_key=api_key, raw_key=raw_key)

    def bootstrap_admin(
        self,
        payload: BootstrapAdminCreate,
        presented_token: str | None,
    ) -> tuple[UserAccount, IssuedCredential]:
        configured_token = self.settings.bootstrap_token
        if configured_token is None or presented_token is None:
            raise AuthenticationError("Administrator bootstrap is not authorized.")
        if not hmac.compare_digest(
            configured_token.get_secret_value(),
            presented_token,
        ):
            raise AuthenticationError("Administrator bootstrap is not authorized.")
        if self.repository.count_users() != 0:
            raise AuthConflictError(
                "Administrator bootstrap has already been completed."
            )
        try:
            user = self.repository.create_user(
                UserCreate(
                    email=payload.email,
                    display_name=payload.display_name,
                    role="admin",
                )
            )
            credential = self._issue_api_key(
                user,
                ApiKeyCreate(label="bootstrap-admin"),
            )
        except IntegrityError as error:
            raise AuthConflictError(
                "Administrator bootstrap conflicts with existing identity data."
            ) from error
        return user, credential

    def create_user(self, payload: UserCreate) -> UserAccount:
        if self.repository.get_user_by_email(payload.email) is not None:
            raise AuthConflictError(
                f"A user with email '{payload.email}' already exists."
            )
        try:
            return self.repository.create_user(payload)
        except IntegrityError as error:
            raise AuthConflictError(
                "The user conflicts with an existing identity."
            ) from error

    def get_user(self, user_id: UUID) -> UserAccount:
        user = self.repository.get_user(user_id)
        if user is None:
            raise AuthNotFoundError(f"User '{user_id}' was not found.")
        return user

    def list_users(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[UserAccount]:
        return self.repository.list_users(offset=offset, limit=limit)

    def issue_api_key(
        self,
        user_id: UUID,
        payload: ApiKeyCreate,
    ) -> IssuedCredential:
        return self._issue_api_key(self.get_user(user_id), payload)

    def list_api_keys(self, user_id: UUID) -> list[ApiKey]:
        self.get_user(user_id)
        return self.repository.list_api_keys(user_id)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    def authenticate(self, raw_key: str) -> ApiKey:
        if not raw_key.startswith("msk_"):
            raise AuthenticationError("Invalid or inactive API key.")
        key_hash = self.hash_api_key(raw_key, self.settings.api_key_pepper)
        api_key = self.repository.get_api_key_by_hash(key_hash)
        now = datetime.now(UTC)
        if (
            api_key is None
            or api_key.revoked_at is not None
            or not api_key.user.is_active
            or (
                api_key.expires_at is not None
                and self._as_utc(api_key.expires_at) <= now
            )
        ):
            raise AuthenticationError("Invalid or inactive API key.")
        return self.repository.record_use(api_key)

    def revoke_api_key(self, api_key_id: UUID) -> ApiKey:
        api_key = self.repository.get_api_key(api_key_id)
        if api_key is None:
            raise AuthNotFoundError(f"API key '{api_key_id}' was not found.")
        if api_key.revoked_at is not None:
            raise AuthConflictError("The API key has already been revoked.")
        return self.repository.revoke(api_key)
