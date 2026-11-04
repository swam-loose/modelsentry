from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

RoleName = Literal["admin", "operator", "reviewer", "viewer"]
PermissionName = Literal["admin", "operate", "read", "review"]
EmailAddress = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=3,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]
DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
ApiKeyLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class UtcTimestampModel(BaseModel):
    """Render timezone-naive SQLite timestamps as explicit UTC values."""

    @field_validator("*", mode="after")
    @classmethod
    def normalize_datetime(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class BootstrapAdminCreate(BaseModel):
    """Initial administrator accepted only before any user exists."""

    email: EmailAddress
    display_name: DisplayName

    model_config = ConfigDict(extra="forbid")


class UserCreate(BaseModel):
    """Administrator-managed local identity."""

    email: EmailAddress
    display_name: DisplayName
    role: RoleName

    model_config = ConfigDict(extra="forbid")


class UserRead(UtcTimestampModel):
    """Public user metadata without credential material."""

    id: UUID
    email: str
    display_name: str
    role: RoleName
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreate(BaseModel):
    """Metadata for a new credential whose secret is returned once."""

    label: ApiKeyLabel
    expires_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("expires_at")
    @classmethod
    def normalize_expiry(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class ApiKeyRead(UtcTimestampModel):
    """Credential metadata that never exposes the stored digest."""

    id: UUID
    user_id: UUID
    label: str
    key_prefix: str
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IssuedApiKeyRead(ApiKeyRead):
    """One-time credential response; api_key is never returned again."""

    api_key: str = Field(min_length=32)


class BootstrapAdminRead(BaseModel):
    """Initial administrator and its one-time API key."""

    user: UserRead
    credential: IssuedApiKeyRead


class CurrentPrincipalRead(BaseModel):
    """Authenticated identity and effective permission labels."""

    user: UserRead
    api_key_id: UUID
    permissions: list[PermissionName]
