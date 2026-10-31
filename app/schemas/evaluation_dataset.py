from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
)

DatasetName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
DatasetSlug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
DatasetDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=1000),
]
DatasetChangeNote = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
EvaluationCaseKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9]+(?:[A-Za-z0-9._-]*[A-Za-z0-9])?$",
    ),
]


class EvaluationCaseCreate(BaseModel):
    """One validated evaluation case supplied through JSON or JSONL."""

    case_key: EvaluationCaseKey
    input: dict[str, JsonValue]
    expected_output: JsonValue | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class EvaluationDatasetVersionCreate(BaseModel):
    """Input accepted when creating an immutable dataset version."""

    cases: list[EvaluationCaseCreate] = Field(min_length=1, max_length=10_000)
    change_note: DatasetChangeNote | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("cases")
    @classmethod
    def case_keys_must_be_unique(
        cls,
        cases: list[EvaluationCaseCreate],
    ) -> list[EvaluationCaseCreate]:
        keys = [case.case_key for case in cases]
        if len(keys) != len(set(keys)):
            raise ValueError("Evaluation case keys must be unique.")
        return cases


class EvaluationDatasetCreate(BaseModel):
    """Input accepted when registering evaluation dataset metadata."""

    name: DatasetName
    slug: DatasetSlug
    description: DatasetDescription | None = None

    model_config = ConfigDict(extra="forbid")


class EvaluationCaseRead(BaseModel):
    """Public representation of a persisted evaluation case."""

    id: UUID
    dataset_version_id: UUID
    position: int
    case_key: str
    input: dict[str, JsonValue] = Field(
        validation_alias=AliasChoices("input_data", "input")
    )
    expected_output: JsonValue | None
    metadata: dict[str, JsonValue] = Field(
        validation_alias=AliasChoices("case_metadata", "metadata")
    )
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationDatasetVersionRead(BaseModel):
    """Public summary of an immutable dataset version."""

    id: UUID
    dataset_id: UUID
    version: int
    content_sha256: str
    case_count: int
    change_note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationDatasetVersionDetailRead(EvaluationDatasetVersionRead):
    """Dataset version summary together with its ordered cases."""

    cases: list[EvaluationCaseRead]


class EvaluationDatasetRead(BaseModel):
    """Public representation of evaluation dataset metadata."""

    id: UUID
    name: str
    slug: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationDatasetDetailRead(EvaluationDatasetRead):
    """Dataset metadata together with its version history."""

    versions: list[EvaluationDatasetVersionRead]
