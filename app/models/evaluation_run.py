from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evaluation_dataset import (
        EvaluationCase,
        EvaluationDatasetVersion,
    )
    from app.models.human_review import HumanReview
    from app.models.prompt import PromptVersion
    from app.models.registered_model import RegisteredModel


class EvaluationRun(Base):
    """A reproducible execution against fixed model, prompt, and dataset versions."""

    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_evaluation_runs_status",
        ),
        CheckConstraint(
            "total_cases >= 0",
            name="ck_evaluation_runs_nonnegative_total_cases",
        ),
        CheckConstraint(
            "succeeded_cases >= 0",
            name="ck_evaluation_runs_nonnegative_succeeded_cases",
        ),
        CheckConstraint(
            "errored_cases >= 0",
            name="ck_evaluation_runs_nonnegative_errored_cases",
        ),
        CheckConstraint(
            "passed_cases >= 0",
            name="ck_evaluation_runs_nonnegative_passed_cases",
        ),
        CheckConstraint(
            "failed_cases >= 0",
            name="ck_evaluation_runs_nonnegative_failed_cases",
        ),
        CheckConstraint(
            "passed_cases + failed_cases <= succeeded_cases",
            name="ck_evaluation_runs_evaluated_within_succeeded",
        ),
        CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0",
            name="ck_evaluation_runs_nonnegative_tokens",
        ),
        CheckConstraint(
            "total_latency_ms >= 0 AND average_latency_ms >= 0 AND p95_latency_ms >= 0",
            name="ck_evaluation_runs_nonnegative_latency_metrics",
        ),
        CheckConstraint(
            "estimated_cost_usd >= 0 AND input_cost_per_million >= 0 "
            "AND output_cost_per_million >= 0",
            name="ck_evaluation_runs_nonnegative_cost_metrics",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    registered_model_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("registered_models.id"),
        nullable=False,
        index=True,
    )
    prompt_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("prompt_versions.id"),
        nullable=False,
        index=True,
    )
    dataset_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_dataset_versions.id"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    total_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    succeeded_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    errored_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    passed_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    failed_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    average_latency_ms: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    p95_latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    input_cost_per_million: Mapped[Decimal] = mapped_column(
        Numeric(14, 6),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    output_cost_per_million: Mapped[Decimal] = mapped_column(
        Numeric(14, 6),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    token_usage_estimated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    registered_model: Mapped[RegisteredModel] = relationship()
    prompt_version: Mapped[PromptVersion] = relationship()
    dataset_version: Mapped[EvaluationDatasetVersion] = relationship()
    results: Mapped[list[EvaluationResult]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="EvaluationResult.position",
    )
    reviews: Mapped[list[HumanReview]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="HumanReview.created_at, HumanReview.id",
    )

    @property
    def evaluated_cases(self) -> int:
        """Number of successful provider results with deterministic expectations."""

        return self.passed_cases + self.failed_cases

    @property
    def pass_rate(self) -> float | None:
        """Share of evaluated cases that passed every configured policy."""

        if self.evaluated_cases == 0:
            return None
        return self.passed_cases / self.evaluated_cases

    @property
    def total_tokens(self) -> int:
        """Combined input and output token usage."""

        return self.input_tokens + self.output_tokens

    @property
    def approval_status(self) -> str:
        """Conservative aggregate of all immutable human review decisions."""

        if not self.reviews:
            return "not_requested"
        statuses = {review.status for review in self.reviews}
        if "rejected" in statuses:
            return "rejected"
        if "pending" in statuses:
            return "pending"
        return "approved"


class EvaluationResult(Base):
    """One provider response or rendering error for an evaluation case."""

    __tablename__ = "evaluation_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('succeeded', 'error')",
            name="ck_evaluation_results_status",
        ),
        CheckConstraint(
            "evaluation_status IN ('not_evaluated', 'passed', 'failed')",
            name="ck_evaluation_results_evaluation_status",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_evaluation_results_nonnegative_position",
        ),
        CheckConstraint(
            "latency_ms >= 0",
            name="ck_evaluation_results_nonnegative_latency",
        ),
        CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0",
            name="ck_evaluation_results_nonnegative_tokens",
        ),
        CheckConstraint(
            "estimated_cost_usd >= 0",
            name="ck_evaluation_results_nonnegative_cost",
        ),
        UniqueConstraint(
            "run_id",
            "evaluation_case_id",
            name="uq_evaluation_results_run_case",
        ),
        UniqueConstraint(
            "run_id",
            "position",
            name="uq_evaluation_results_run_position",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evaluation_case_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_cases.id"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    evaluation_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="not_evaluated",
        server_default="not_evaluated",
    )
    rendered_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    rendered_user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    token_usage_estimated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    run: Mapped[EvaluationRun] = relationship(back_populates="results")
    evaluation_case: Mapped[EvaluationCase] = relationship()
    checks: Mapped[list[EvaluationCheck]] = relationship(
        back_populates="evaluation_result",
        cascade="all, delete-orphan",
        order_by="EvaluationCheck.position",
    )

    @property
    def total_tokens(self) -> int:
        """Combined input and output token usage for this result."""

        return self.input_tokens + self.output_tokens


class EvaluationCheck(Base):
    """Persisted evidence from one deterministic evaluator."""

    __tablename__ = "evaluation_checks"
    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_evaluation_checks_nonnegative_position",
        ),
        UniqueConstraint(
            "evaluation_result_id",
            "position",
            name="uq_evaluation_checks_result_position",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    evaluation_result_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluator_type: Mapped[str] = mapped_column(String(40), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    expected_value: Mapped[object] = mapped_column(JSON, nullable=False)
    actual_value: Mapped[object] = mapped_column(JSON, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    evaluation_result: Mapped[EvaluationResult] = relationship(back_populates="checks")
