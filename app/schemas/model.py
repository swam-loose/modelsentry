from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

ModelProvider = Literal["mock", "ollama"]
ModelName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
ModelSlug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
ModelIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
ModelDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=1000),
]


class RegisteredModelCreate(BaseModel):
    """Input accepted when registering an evaluation model."""

    name: ModelName
    slug: ModelSlug
    provider: ModelProvider = "mock"
    model_identifier: ModelIdentifier
    description: ModelDescription | None = None

    model_config = ConfigDict(extra="forbid")


class RegisteredModelRead(BaseModel):
    """Public representation of a registered evaluation model."""

    id: UUID
    name: str
    slug: str
    provider: ModelProvider
    model_identifier: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
