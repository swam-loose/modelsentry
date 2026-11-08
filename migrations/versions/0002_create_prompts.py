"""Create prompts and immutable prompt versions.

Revision ID: 0002_prompts
Revises: 0001_registered_models
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_prompts"
down_revision: str | Sequence[str] | None = "0001_registered_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the versioned prompt registry schema."""

    op.create_table(
        "prompts",
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
    op.create_index(op.f("ix_prompts_slug"), "prompts", ["slug"], unique=True)

    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("prompt_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_prompt_versions_positive_version",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_id"],
            ["prompts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "prompt_id",
            "version",
            name="uq_prompt_versions_prompt_version",
        ),
    )
    op.create_index(
        op.f("ix_prompt_versions_prompt_id"),
        "prompt_versions",
        ["prompt_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the versioned prompt registry schema."""

    op.drop_index(
        op.f("ix_prompt_versions_prompt_id"),
        table_name="prompt_versions",
    )
    op.drop_table("prompt_versions")
    op.drop_index(op.f("ix_prompts_slug"), table_name="prompts")
    op.drop_table("prompts")
