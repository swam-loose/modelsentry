"""Create human review assignments and final decisions.

Revision ID: 0006_human_reviews
Revises: 0005_deterministic_evaluators
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_human_reviews"
down_revision: str | Sequence[str] | None = "0005_deterministic_evaluators"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the auditable human review queue."""

    op.create_table(
        "human_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer", sa.String(length=160), nullable=False),
        sa.Column("reviewer_role", sa.String(length=80), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'pending' AND decided_at IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_at IS NOT NULL)",
            name="ck_human_reviews_decision_timestamp",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_human_reviews_status",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["evaluation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "reviewer",
            name="uq_human_reviews_run_reviewer",
        ),
    )
    op.create_index(
        op.f("ix_human_reviews_run_id"),
        "human_reviews",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the human review queue."""

    op.drop_index(
        op.f("ix_human_reviews_run_id"),
        table_name="human_reviews",
    )
    op.drop_table("human_reviews")
