from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

EvaluationRunStatus = Literal["pending", "running", "completed", "failed"]
EvaluationResultStatus = Literal["succeeded", "error"]


class EvaluationRunCreate(BaseModel):
    """References required to execute one reproducible evaluation run."""

    registered_model_id: UUID
    prompt_version_id: UUID
    dataset_version_id: UUID

    model_config = ConfigDict(extra="forbid")


class EvaluationResultRead(BaseModel):
    """Public representation of one case-level provider result."""

    id: UUID
    run_id: UUID
    evaluation_case_id: UUID
    position: int
    status: EvaluationResultStatus
    rendered_system_prompt: str | None
    rendered_user_prompt: str
    output_text: str | None
    error_message: str | None
    latency_ms: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationRunRead(BaseModel):
    """Public summary of an evaluation run."""

    id: UUID
    registered_model_id: UUID
    prompt_version_id: UUID
    dataset_version_id: UUID
    provider: str
    model_identifier: str
    status: EvaluationRunStatus
    total_cases: int
    succeeded_cases: int
    errored_cases: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class EvaluationRunDetailRead(EvaluationRunRead):
    """Evaluation run summary together with ordered case-level results."""

    results: list[EvaluationResultRead]
