from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.human_review import ApprovalStatus

ComparisonOutcome = Literal[
    "improved",
    "regressed",
    "mixed",
    "unchanged",
    "inconclusive",
]
CaseOutcome = Literal["passed", "failed", "not_evaluated", "error"]
CaseQualityChange = Literal[
    "improved",
    "regressed",
    "unchanged",
    "inconclusive",
]


class RunComparisonCreate(BaseModel):
    """Two completed runs to compare using the same dataset version."""

    baseline_run_id: UUID
    candidate_run_id: UUID

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def require_distinct_runs(self) -> "RunComparisonCreate":
        if self.baseline_run_id == self.candidate_run_id:
            raise ValueError("Baseline and candidate runs must be different.")
        return self


class RunMetricSnapshot(BaseModel):
    """Quality, performance, usage, and governance evidence for one run."""

    run_id: UUID
    model_identifier: str
    passed_cases: int
    failed_cases: int
    errored_cases: int
    pass_rate: float | None
    average_latency_ms: Decimal
    p95_latency_ms: int
    total_latency_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: Decimal
    token_usage_estimated: bool
    approval_status: ApprovalStatus


class RunMetricDelta(BaseModel):
    """Candidate minus baseline; negative latency and cost deltas are faster/cheaper."""

    pass_rate: float | None
    average_latency_ms: Decimal
    p95_latency_ms: int
    total_latency_ms: int
    total_tokens: int
    estimated_cost_usd: Decimal


class CaseComparisonRead(BaseModel):
    """Case-level evidence aligned by immutable evaluation case identifier."""

    evaluation_case_id: UUID
    position: int
    baseline_outcome: CaseOutcome
    candidate_outcome: CaseOutcome
    quality_change: CaseQualityChange
    latency_delta_ms: int
    token_delta: int
    estimated_cost_delta_usd: Decimal


class RunComparisonRead(BaseModel):
    """Deterministic A/B comparison without an automatic release decision."""

    baseline: RunMetricSnapshot
    candidate: RunMetricSnapshot
    delta: RunMetricDelta
    quality_outcome: ComparisonOutcome
    performance_outcome: ComparisonOutcome
    overall_outcome: ComparisonOutcome
    improved_cases: int
    regressed_cases: int
    unchanged_cases: int
    inconclusive_cases: int
    cases: list[CaseComparisonRead]
