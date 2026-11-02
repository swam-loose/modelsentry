from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from app.schemas.human_review import ApprovalStatus, HumanReviewRead

EvaluationRunStatus = Literal["pending", "running", "completed", "failed"]
EvaluationResultStatus = Literal["succeeded", "error"]
DeterministicEvaluationStatus = Literal["not_evaluated", "passed", "failed"]


class EvaluationRunCreate(BaseModel):
    """References required to execute one reproducible evaluation run."""

    registered_model_id: UUID
    prompt_version_id: UUID
    dataset_version_id: UUID

    model_config = ConfigDict(extra="forbid")


class EvaluationCheckRead(BaseModel):
    """Evidence emitted by one deterministic evaluator."""

    id: UUID
    evaluation_result_id: UUID
    position: int
    evaluator_type: str
    passed: bool
    expected_value: JsonValue
    actual_value: JsonValue
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationResultRead(BaseModel):
    """Public representation of one case-level provider result."""

    id: UUID
    run_id: UUID
    evaluation_case_id: UUID
    position: int
    status: EvaluationResultStatus
    evaluation_status: DeterministicEvaluationStatus
    rendered_system_prompt: str | None
    rendered_user_prompt: str
    output_text: str | None
    error_message: str | None
    latency_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: Decimal
    token_usage_estimated: bool
    created_at: datetime
    checks: list[EvaluationCheckRead]

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
    passed_cases: int
    failed_cases: int
    evaluated_cases: int
    pass_rate: float | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    total_latency_ms: int
    average_latency_ms: Decimal
    p95_latency_ms: int
    estimated_cost_usd: Decimal
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal
    token_usage_estimated: bool
    approval_status: ApprovalStatus
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class EvaluationRunDetailRead(EvaluationRunRead):
    """Evaluation run summary together with ordered case-level results."""

    results: list[EvaluationResultRead]
    reviews: list[HumanReviewRead]
