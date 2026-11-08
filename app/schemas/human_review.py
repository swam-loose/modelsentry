from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

HumanReviewStatus = Literal["pending", "approved", "rejected"]
ApprovalStatus = Literal["not_requested", "pending", "approved", "rejected"]
ReviewerIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
ReviewerRole = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]
ReviewRationale = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000),
]


class HumanReviewCreate(BaseModel):
    """Assign one human reviewer to a completed evaluation run."""

    run_id: UUID
    reviewer: ReviewerIdentifier
    reviewer_role: ReviewerRole | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("reviewer")
    @classmethod
    def normalize_reviewer(cls, reviewer: str) -> str:
        return reviewer.casefold()


class HumanReviewDecision(BaseModel):
    """Submit one final human approval or rejection decision."""

    decision: Literal["approved", "rejected"]
    rationale: ReviewRationale | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def rejection_requires_rationale(self) -> "HumanReviewDecision":
        if self.decision == "rejected" and self.rationale is None:
            raise ValueError("A rationale is required when rejecting a run.")
        return self


class HumanReviewRead(BaseModel):
    """Public representation of an assigned human review."""

    id: UUID
    run_id: UUID
    reviewer: str
    reviewer_role: str | None
    status: HumanReviewStatus
    rationale: str | None
    created_at: datetime
    decided_at: datetime | None
    decided_by_user_id: UUID | None

    model_config = ConfigDict(from_attributes=True)
