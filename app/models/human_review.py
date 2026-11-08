from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evaluation_run import EvaluationRun


class HumanReview(Base):
    """One assigned, auditable human decision for an evaluation run."""

    __tablename__ = "human_reviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_human_reviews_status",
        ),
        CheckConstraint(
            "(status = 'pending' AND decided_at IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_at IS NOT NULL)",
            name="ck_human_reviews_decision_timestamp",
        ),
        UniqueConstraint(
            "run_id",
            "reviewer",
            name="uq_human_reviews_run_reviewer",
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
    reviewer: Mapped[str] = mapped_column(String(160), nullable=False)
    reviewer_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_accounts.id", name="fk_human_reviews_decided_by_user"),
        nullable=True,
        index=True,
    )
    run: Mapped[EvaluationRun] = relationship(back_populates="reviews")
