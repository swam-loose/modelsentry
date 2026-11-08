"""Add token, latency, and estimated cost metrics for run comparisons.

Revision ID: 0007_run_comparison_metrics
Revises: 0006_human_reviews
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_run_comparison_metrics"
down_revision: str | Sequence[str] | None = "0006_human_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist pricing snapshots and aggregate/case-level usage metrics."""

    with op.batch_alter_table("registered_models") as batch_op:
        batch_op.add_column(
            sa.Column(
                "input_cost_per_million",
                sa.Numeric(precision=14, scale=6),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "output_cost_per_million",
                sa.Numeric(precision=14, scale=6),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_registered_models_nonnegative_input_cost",
            "input_cost_per_million >= 0",
        )
        batch_op.create_check_constraint(
            "ck_registered_models_nonnegative_output_cost",
            "output_cost_per_million >= 0",
        )

    with op.batch_alter_table("evaluation_runs") as batch_op:
        batch_op.add_column(
            sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "total_latency_ms",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "average_latency_ms",
                sa.Numeric(precision=12, scale=3),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "p95_latency_ms",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "estimated_cost_usd",
                sa.Numeric(precision=18, scale=8),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "input_cost_per_million",
                sa.Numeric(precision=14, scale=6),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "output_cost_per_million",
                sa.Numeric(precision=14, scale=6),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "token_usage_estimated",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_evaluation_runs_nonnegative_tokens",
            "input_tokens >= 0 AND output_tokens >= 0",
        )
        batch_op.create_check_constraint(
            "ck_evaluation_runs_nonnegative_latency_metrics",
            "total_latency_ms >= 0 AND average_latency_ms >= 0 AND p95_latency_ms >= 0",
        )
        batch_op.create_check_constraint(
            "ck_evaluation_runs_nonnegative_cost_metrics",
            "estimated_cost_usd >= 0 AND input_cost_per_million >= 0 "
            "AND output_cost_per_million >= 0",
        )

    with op.batch_alter_table("evaluation_results") as batch_op:
        batch_op.add_column(
            sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "estimated_cost_usd",
                sa.Numeric(precision=18, scale=8),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "token_usage_estimated",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_evaluation_results_nonnegative_tokens",
            "input_tokens >= 0 AND output_tokens >= 0",
        )
        batch_op.create_check_constraint(
            "ck_evaluation_results_nonnegative_cost",
            "estimated_cost_usd >= 0",
        )


def downgrade() -> None:
    """Remove run comparison metrics and model pricing metadata."""

    with op.batch_alter_table("evaluation_results") as batch_op:
        batch_op.drop_constraint(
            "ck_evaluation_results_nonnegative_cost",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_evaluation_results_nonnegative_tokens",
            type_="check",
        )
        batch_op.drop_column("token_usage_estimated")
        batch_op.drop_column("estimated_cost_usd")
        batch_op.drop_column("output_tokens")
        batch_op.drop_column("input_tokens")

    with op.batch_alter_table("evaluation_runs") as batch_op:
        batch_op.drop_constraint(
            "ck_evaluation_runs_nonnegative_cost_metrics",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_evaluation_runs_nonnegative_latency_metrics",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_evaluation_runs_nonnegative_tokens",
            type_="check",
        )
        batch_op.drop_column("token_usage_estimated")
        batch_op.drop_column("output_cost_per_million")
        batch_op.drop_column("input_cost_per_million")
        batch_op.drop_column("estimated_cost_usd")
        batch_op.drop_column("p95_latency_ms")
        batch_op.drop_column("average_latency_ms")
        batch_op.drop_column("total_latency_ms")
        batch_op.drop_column("output_tokens")
        batch_op.drop_column("input_tokens")

    with op.batch_alter_table("registered_models") as batch_op:
        batch_op.drop_constraint(
            "ck_registered_models_nonnegative_output_cost",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_registered_models_nonnegative_input_cost",
            type_="check",
        )
        batch_op.drop_column("output_cost_per_million")
        batch_op.drop_column("input_cost_per_million")
