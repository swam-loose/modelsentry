"""Create versioned evaluation datasets and cases.

Revision ID: 0003_evaluation_datasets
Revises: 0002_prompts
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_evaluation_datasets"
down_revision: str | Sequence[str] | None = "0002_prompts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create evaluation dataset metadata, versions, and cases."""

    op.create_table(
        "evaluation_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
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
    )
    op.create_index(
        op.f("ix_evaluation_datasets_slug"),
        "evaluation_datasets",
        ["slug"],
        unique=True,
    )

    op.create_table(
        "evaluation_dataset_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "case_count > 0",
            name="ck_evaluation_dataset_versions_positive_case_count",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_evaluation_dataset_versions_positive_version",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["evaluation_datasets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_id",
            "content_sha256",
            name="uq_evaluation_dataset_versions_dataset_hash",
        ),
        sa.UniqueConstraint(
            "dataset_id",
            "version",
            name="uq_evaluation_dataset_versions_dataset_version",
        ),
    )
    op.create_index(
        op.f("ix_evaluation_dataset_versions_dataset_id"),
        "evaluation_dataset_versions",
        ["dataset_id"],
        unique=False,
    )

    op.create_table(
        "evaluation_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("case_key", sa.String(length=120), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("expected_output", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_evaluation_cases_nonnegative_position",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["evaluation_dataset_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_version_id",
            "case_key",
            name="uq_evaluation_cases_version_key",
        ),
        sa.UniqueConstraint(
            "dataset_version_id",
            "position",
            name="uq_evaluation_cases_version_position",
        ),
    )
    op.create_index(
        op.f("ix_evaluation_cases_dataset_version_id"),
        "evaluation_cases",
        ["dataset_version_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove evaluation dataset metadata, versions, and cases."""

    op.drop_index(
        op.f("ix_evaluation_cases_dataset_version_id"),
        table_name="evaluation_cases",
    )
    op.drop_table("evaluation_cases")
    op.drop_index(
        op.f("ix_evaluation_dataset_versions_dataset_id"),
        table_name="evaluation_dataset_versions",
    )
    op.drop_table("evaluation_dataset_versions")
    op.drop_index(
        op.f("ix_evaluation_datasets_slug"),
        table_name="evaluation_datasets",
    )
    op.drop_table("evaluation_datasets")
