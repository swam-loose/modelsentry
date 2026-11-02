"""Add deterministic evaluator evidence and run quality counts.

Revision ID: 0005_deterministic_evaluators
Revises: 0004_evaluation_runs
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_deterministic_evaluators"
down_revision: str | Sequence[str] | None = "0004_evaluation_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist deterministic case outcomes and evaluator-level evidence."""

    with op.batch_alter_table("evaluation_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "passed_cases",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "failed_cases",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_evaluation_runs_nonnegative_passed_cases",
            "passed_cases >= 0",
        )
        batch_op.create_check_constraint(
            "ck_evaluation_runs_nonnegative_failed_cases",
            "failed_cases >= 0",
        )
        batch_op.create_check_constraint(
            "ck_evaluation_runs_evaluated_within_succeeded",
            "passed_cases + failed_cases <= succeeded_cases",
        )

    with op.batch_alter_table("evaluation_results") as batch_op:
        batch_op.add_column(
            sa.Column(
                "evaluation_status",
                sa.String(length=20),
                server_default="not_evaluated",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_evaluation_results_evaluation_status",
            "evaluation_status IN ('not_evaluated', 'passed', 'failed')",
        )

    op.create_table(
        "evaluation_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_result_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("evaluator_type", sa.String(length=40), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("expected_value", sa.JSON(), nullable=False),
        sa.Column("actual_value", sa.JSON(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_evaluation_checks_nonnegative_position",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_result_id"],
            ["evaluation_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_result_id",
            "position",
            name="uq_evaluation_checks_result_position",
        ),
    )
    op.create_index(
        op.f("ix_evaluation_checks_evaluation_result_id"),
        "evaluation_checks",
        ["evaluation_result_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove deterministic evaluator evidence and quality counts."""

    op.drop_index(
        op.f("ix_evaluation_checks_evaluation_result_id"),
        table_name="evaluation_checks",
    )
    op.drop_table("evaluation_checks")

    with op.batch_alter_table("evaluation_results") as batch_op:
        batch_op.drop_constraint(
            "ck_evaluation_results_evaluation_status",
            type_="check",
        )
        batch_op.drop_column("evaluation_status")

    with op.batch_alter_table("evaluation_runs") as batch_op:
        batch_op.drop_constraint(
            "ck_evaluation_runs_evaluated_within_succeeded",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_evaluation_runs_nonnegative_failed_cases",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_evaluation_runs_nonnegative_passed_cases",
            type_="check",
        )
        batch_op.drop_column("failed_cases")
        batch_op.drop_column("passed_cases")
