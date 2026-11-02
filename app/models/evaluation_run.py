from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
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


class EvaluationResult(Base):
    """One provider response or rendering error for an evaluation case."""

    __tablename__ = "evaluation_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('succeeded', 'error')",
            name="ck_evaluation_results_status",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_evaluation_results_nonnegative_position",
        ),
        CheckConstraint(
            "latency_ms >= 0",
            name="ck_evaluation_results_nonnegative_latency",
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
    rendered_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    rendered_user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    run: Mapped[EvaluationRun] = relationship(back_populates="results")
    evaluation_case: Mapped[EvaluationCase] = relationship()
