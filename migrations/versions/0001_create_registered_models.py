"""Create the registered models table.

Revision ID: 0001_registered_models
Revises:
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_registered_models"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial ModelSentry registry schema."""

    op.create_table(
        "registered_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=40),
            server_default="mock",
            nullable=False,
        ),
        sa.Column("model_identifier", sa.String(length=200), nullable=False),
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
        sa.CheckConstraint(
            "provider IN ('mock', 'ollama')",
            name="ck_registered_models_provider",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "model_identifier",
            name="uq_registered_models_provider_identifier",
        ),
    )
    op.create_index(
        op.f("ix_registered_models_slug"),
        "registered_models",
        ["slug"],
        unique=True,
    )


def downgrade() -> None:
    """Remove the initial ModelSentry registry schema."""

    op.drop_index(
        op.f("ix_registered_models_slug"),
        table_name="registered_models",
    )
    op.drop_table("registered_models")
