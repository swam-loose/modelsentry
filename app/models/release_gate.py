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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evaluation_run import EvaluationRun


class ReleaseGate(Base):
    """Named governance policy with immutable threshold versions."""

    __tablename__ = "release_gates"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )
    versions: Mapped[list[ReleaseGateVersion]] = relationship(
        back_populates="release_gate",
        cascade="all, delete-orphan",
        order_by="ReleaseGateVersion.version",
    )


class ReleaseGateVersion(Base):
    """Immutable quality, reliability, performance, and review criteria."""

    __tablename__ = "release_gate_versions"
    __table_args__ = (
        CheckConstraint(
            "version > 0",
            name="ck_release_gate_versions_positive_version",
        ),
        CheckConstraint(
            "min_pass_rate >= 0 AND min_pass_rate <= 1",
            name="ck_release_gate_versions_pass_rate_range",
        ),
        CheckConstraint(
            "max_errored_cases >= 0",
            name="ck_release_gate_versions_nonnegative_errors",
        ),
        CheckConstraint(
            "max_average_latency_ms IS NULL OR max_average_latency_ms >= 0",
            name="ck_release_gate_versions_nonnegative_average_latency",
        ),
        CheckConstraint(
            "max_p95_latency_ms IS NULL OR max_p95_latency_ms >= 0",
            name="ck_release_gate_versions_nonnegative_p95_latency",
        ),
        CheckConstraint(
            "max_estimated_cost_usd IS NULL OR max_estimated_cost_usd >= 0",
            name="ck_release_gate_versions_nonnegative_cost",
        ),
        UniqueConstraint(
            "release_gate_id",
            "version",
            name="uq_release_gate_versions_gate_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    release_gate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("release_gates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    min_pass_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        default=Decimal("1"),
        server_default="1",
    )
    max_errored_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    max_average_latency_ms: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3),
        nullable=True,
    )
    max_p95_latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    max_estimated_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8),
        nullable=True,
    )
    require_human_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    require_no_quality_regressions: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    release_gate: Mapped[ReleaseGate] = relationship(back_populates="versions")
    evaluations: Mapped[list[ReleaseGateEvaluation]] = relationship(
        back_populates="release_gate_version",
    )


class ReleaseGateEvaluation(Base):
    """Immutable result of evaluating one candidate against one policy version."""

    __tablename__ = "release_gate_evaluations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('passed', 'failed')",
            name="ck_release_gate_evaluations_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    release_gate_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("release_gate_versions.id"),
        nullable=False,
        index=True,
    )
    candidate_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_runs.id"),
        nullable=False,
        index=True,
    )
    baseline_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_runs.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    release_gate_version: Mapped[ReleaseGateVersion] = relationship(
        back_populates="evaluations"
    )
    candidate_run: Mapped[EvaluationRun] = relationship(foreign_keys=[candidate_run_id])
    baseline_run: Mapped[EvaluationRun | None] = relationship(
        foreign_keys=[baseline_run_id]
    )
    checks: Mapped[list[ReleaseGateCheck]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
        order_by="ReleaseGateCheck.position",
    )


class ReleaseGateCheck(Base):
    """Expected and actual evidence for one release-gate criterion."""

    __tablename__ = "release_gate_checks"
    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_release_gate_checks_nonnegative_position",
        ),
        UniqueConstraint(
            "evaluation_id",
            "position",
            name="uq_release_gate_checks_evaluation_position",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    evaluation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("release_gate_evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    check_type: Mapped[str] = mapped_column(String(60), nullable=False)
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
    evaluation: Mapped[ReleaseGateEvaluation] = relationship(back_populates="checks")
