"""Create evaluation runs and case-level results.

Revision ID: 0004_evaluation_runs
Revises: 0003_evaluation_datasets
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_evaluation_runs"
down_revision: str | Sequence[str] | None = "0003_evaluation_datasets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create evaluation run state and case-level evidence tables."""

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("registered_model_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_version_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model_identifier", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "total_cases",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "succeeded_cases",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "errored_cases",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "errored_cases >= 0",
            name="ck_evaluation_runs_nonnegative_errored_cases",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_evaluation_runs_status",
        ),
        sa.CheckConstraint(
            "succeeded_cases >= 0",
            name="ck_evaluation_runs_nonnegative_succeeded_cases",
        ),
        sa.CheckConstraint(
            "total_cases >= 0",
            name="ck_evaluation_runs_nonnegative_total_cases",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["evaluation_dataset_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"],
            ["prompt_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["registered_model_id"],
            ["registered_models.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evaluation_runs_dataset_version_id"),
        "evaluation_runs",
        ["dataset_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_runs_prompt_version_id"),
        "evaluation_runs",
        ["prompt_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_runs_registered_model_id"),
        "evaluation_runs",
        ["registered_model_id"],
        unique=False,
    )

    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_case_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rendered_system_prompt", sa.Text(), nullable=True),
        sa.Column("rendered_user_prompt", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latency_ms >= 0",
            name="ck_evaluation_results_nonnegative_latency",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_evaluation_results_nonnegative_position",
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'error')",
            name="ck_evaluation_results_status",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_case_id"],
            ["evaluation_cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["evaluation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "evaluation_case_id",
            name="uq_evaluation_results_run_case",
        ),
        sa.UniqueConstraint(
            "run_id",
            "position",
            name="uq_evaluation_results_run_position",
        ),
    )
    op.create_index(
        op.f("ix_evaluation_results_evaluation_case_id"),
        "evaluation_results",
        ["evaluation_case_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_results_run_id"),
        "evaluation_results",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove evaluation run state and case-level evidence tables."""

    op.drop_index(
        op.f("ix_evaluation_results_run_id"),
        table_name="evaluation_results",
    )
    op.drop_index(
        op.f("ix_evaluation_results_evaluation_case_id"),
        table_name="evaluation_results",
    )
    op.drop_table("evaluation_results")
    op.drop_index(
        op.f("ix_evaluation_runs_registered_model_id"),
        table_name="evaluation_runs",
    )
    op.drop_index(
        op.f("ix_evaluation_runs_prompt_version_id"),
        table_name="evaluation_runs",
    )
    op.drop_index(
        op.f("ix_evaluation_runs_dataset_version_id"),
        table_name="evaluation_runs",
    )
    op.drop_table("evaluation_runs")
