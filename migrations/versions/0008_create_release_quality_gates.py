"""Create versioned release quality gates and immutable decisions.

Revision ID: 0008_release_quality_gates
Revises: 0007_run_comparison_metrics
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_release_quality_gates"
down_revision: str | Sequence[str] | None = "0007_run_comparison_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create policy, version, evaluation, and check tables."""

    op.create_table(
        "release_gates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(
        op.f("ix_release_gates_slug"),
        "release_gates",
        ["slug"],
        unique=True,
    )

    op.create_table(
        "release_gate_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("release_gate_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "min_pass_rate",
            sa.Numeric(precision=5, scale=4),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "max_errored_cases",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "max_average_latency_ms",
            sa.Numeric(precision=12, scale=3),
            nullable=True,
        ),
        sa.Column("max_p95_latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "max_estimated_cost_usd",
            sa.Numeric(precision=18, scale=8),
            nullable=True,
        ),
        sa.Column(
            "require_human_approval",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "require_no_quality_regressions",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "max_average_latency_ms IS NULL OR max_average_latency_ms >= 0",
            name="ck_release_gate_versions_nonnegative_average_latency",
        ),
        sa.CheckConstraint(
            "max_errored_cases >= 0",
            name="ck_release_gate_versions_nonnegative_errors",
        ),
        sa.CheckConstraint(
            "max_estimated_cost_usd IS NULL OR max_estimated_cost_usd >= 0",
            name="ck_release_gate_versions_nonnegative_cost",
        ),
        sa.CheckConstraint(
            "max_p95_latency_ms IS NULL OR max_p95_latency_ms >= 0",
            name="ck_release_gate_versions_nonnegative_p95_latency",
        ),
        sa.CheckConstraint(
            "min_pass_rate >= 0 AND min_pass_rate <= 1",
            name="ck_release_gate_versions_pass_rate_range",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_release_gate_versions_positive_version",
        ),
        sa.ForeignKeyConstraint(
            ["release_gate_id"],
            ["release_gates.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_gate_id",
            "version",
            name="uq_release_gate_versions_gate_version",
        ),
    )
    op.create_index(
        op.f("ix_release_gate_versions_release_gate_id"),
        "release_gate_versions",
        ["release_gate_id"],
        unique=False,
    )

    op.create_table(
        "release_gate_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("release_gate_version_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_run_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('passed', 'failed')",
            name="ck_release_gate_evaluations_status",
        ),
        sa.ForeignKeyConstraint(
            ["baseline_run_id"],
            ["evaluation_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["candidate_run_id"],
            ["evaluation_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["release_gate_version_id"],
            ["release_gate_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_release_gate_evaluations_baseline_run_id"),
        "release_gate_evaluations",
        ["baseline_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_release_gate_evaluations_candidate_run_id"),
        "release_gate_evaluations",
        ["candidate_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_release_gate_evaluations_release_gate_version_id"),
        "release_gate_evaluations",
        ["release_gate_version_id"],
        unique=False,
    )

    op.create_table(
        "release_gate_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("check_type", sa.String(length=60), nullable=False),
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
            name="ck_release_gate_checks_nonnegative_position",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["release_gate_evaluations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_id",
            "position",
            name="uq_release_gate_checks_evaluation_position",
        ),
    )
    op.create_index(
        op.f("ix_release_gate_checks_evaluation_id"),
        "release_gate_checks",
        ["evaluation_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove release-gate decisions, versions, and policies."""

    op.drop_index(
        op.f("ix_release_gate_checks_evaluation_id"),
        table_name="release_gate_checks",
    )
    op.drop_table("release_gate_checks")
    op.drop_index(
        op.f("ix_release_gate_evaluations_release_gate_version_id"),
        table_name="release_gate_evaluations",
    )
    op.drop_index(
        op.f("ix_release_gate_evaluations_candidate_run_id"),
        table_name="release_gate_evaluations",
    )
    op.drop_index(
        op.f("ix_release_gate_evaluations_baseline_run_id"),
        table_name="release_gate_evaluations",
    )
    op.drop_table("release_gate_evaluations")
    op.drop_index(
        op.f("ix_release_gate_versions_release_gate_id"),
        table_name="release_gate_versions",
    )
    op.drop_table("release_gate_versions")
    op.drop_index(op.f("ix_release_gates_slug"), table_name="release_gates")
    op.drop_table("release_gates")
