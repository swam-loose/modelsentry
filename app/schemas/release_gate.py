from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
)

GateName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
GateSlug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
GateDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=1000),
]
GateChangeNote = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
PassRateThreshold = Annotated[
    Decimal,
    Field(ge=0, le=1, max_digits=5, decimal_places=4),
]
LatencyThreshold = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=3),
]
CostThreshold = Annotated[
    Decimal,
    Field(ge=0, max_digits=18, decimal_places=8),
]
ReleaseGateEvaluationStatus = Literal["passed", "failed"]


class UtcTimestampModel(BaseModel):
    """Normalize SQLite's timezone-naive timestamps as UTC API values."""

    @field_validator("*", mode="after")
    @classmethod
    def normalize_datetime(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class ReleaseGateVersionCreate(BaseModel):
    """Criteria accepted when creating an immutable gate version."""

    min_pass_rate: PassRateThreshold = Decimal("1")
    max_errored_cases: int = Field(default=0, ge=0)
    max_average_latency_ms: LatencyThreshold | None = None
    max_p95_latency_ms: int | None = Field(default=None, ge=0)
    max_estimated_cost_usd: CostThreshold | None = None
    require_human_approval: bool = True
    require_no_quality_regressions: bool = True
    change_note: GateChangeNote | None = None

    model_config = ConfigDict(extra="forbid")


class ReleaseGateCreate(BaseModel):
    """Input accepted when registering a release gate and version one."""

    name: GateName
    slug: GateSlug
    description: GateDescription | None = None
    initial_version: ReleaseGateVersionCreate = Field(
        default_factory=ReleaseGateVersionCreate
    )

    model_config = ConfigDict(extra="forbid")


class ReleaseGateVersionRead(UtcTimestampModel):
    """Public representation of immutable gate criteria."""

    id: UUID
    release_gate_id: UUID
    version: int
    min_pass_rate: Decimal
    max_errored_cases: int
    max_average_latency_ms: Decimal | None
    max_p95_latency_ms: int | None
    max_estimated_cost_usd: Decimal | None
    require_human_approval: bool
    require_no_quality_regressions: bool
    change_note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReleaseGateRead(UtcTimestampModel):
    """Public release-gate registry metadata."""

    id: UUID
    name: str
    slug: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReleaseGateDetailRead(ReleaseGateRead):
    """Release-gate metadata and complete immutable version history."""

    versions: list[ReleaseGateVersionRead]


class ReleaseGateEvaluationCreate(BaseModel):
    """Candidate and optional baseline used for one immutable evaluation."""

    candidate_run_id: UUID
    baseline_run_id: UUID | None = None

    model_config = ConfigDict(extra="forbid")


class ReleaseGateCheckRead(UtcTimestampModel):
    """One expected-versus-actual policy decision with supporting evidence."""

    id: UUID
    evaluation_id: UUID
    position: int
    check_type: str
    passed: bool
    expected_value: JsonValue
    actual_value: JsonValue
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReleaseGateEvaluationRead(UtcTimestampModel):
    """Immutable gate decision; it does not deploy or promote a model."""

    id: UUID
    release_gate_version_id: UUID
    candidate_run_id: UUID
    baseline_run_id: UUID | None
    status: ReleaseGateEvaluationStatus
    created_at: datetime
    checks: list[ReleaseGateCheckRead]

    model_config = ConfigDict(from_attributes=True)
