from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

PromptName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
PromptSlug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
PromptDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=1000),
]
PromptText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20000),
]
PromptChangeNote = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
PromptVariable = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
    ),
]


class PromptVersionCreate(BaseModel):
    """Input accepted when adding an immutable prompt version."""

    system_prompt: PromptText | None = None
    user_prompt_template: PromptText
    variables: list[PromptVariable] = Field(default_factory=list, max_length=50)
    change_note: PromptChangeNote | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("variables")
    @classmethod
    def variables_must_be_unique(cls, variables: list[str]) -> list[str]:
        if len(variables) != len(set(variables)):
            raise ValueError("Prompt variables must be unique.")
        return variables


class PromptCreate(BaseModel):
    """Input accepted when creating a prompt and its first version."""

    name: PromptName
    slug: PromptSlug
    description: PromptDescription | None = None
    initial_version: PromptVersionCreate

    model_config = ConfigDict(extra="forbid")


class PromptVersionRead(BaseModel):
    """Public representation of an immutable prompt version."""

    id: UUID
    prompt_id: UUID
    version: int
    system_prompt: str | None
    user_prompt_template: str
    variables: list[str]
    change_note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptRead(BaseModel):
    """Public representation of prompt registry metadata."""

    id: UUID
    name: str
    slug: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptDetailRead(PromptRead):
    """Prompt metadata together with its complete version history."""

    versions: list[PromptVersionRead]
