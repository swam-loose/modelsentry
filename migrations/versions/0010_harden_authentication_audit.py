"""Make administrator bootstrap atomic and retain review-decision actors.

Revision ID: 0010_authentication_audit
Revises: 0009_authentication_rbac
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_authentication_audit"
down_revision: str | Sequence[str] | None = "0009_authentication_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Preserve legacy rows while adding the bootstrap guard and actor IDs."""

    with op.batch_alter_table("user_accounts") as batch:
        batch.add_column(sa.Column("bootstrap_slot", sa.Integer(), nullable=True))
        batch.create_check_constraint(
            "ck_user_accounts_bootstrap_slot",
            "bootstrap_slot IS NULL OR (bootstrap_slot = 1 AND role = 'admin')",
        )
        batch.create_unique_constraint(
            "uq_user_accounts_bootstrap_slot", ["bootstrap_slot"]
        )
    with op.batch_alter_table("human_reviews") as batch:
        batch.add_column(sa.Column("decided_by_user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_human_reviews_decided_by_user",
            "user_accounts",
            ["decided_by_user_id"],
            ["id"],
        )
        batch.create_index(
            "ix_human_reviews_decided_by_user_id", ["decided_by_user_id"]
        )


def downgrade() -> None:
    """Remove only the new audit columns, retaining legacy application data."""

    with op.batch_alter_table("human_reviews") as batch:
        batch.drop_index("ix_human_reviews_decided_by_user_id")
        batch.drop_constraint("fk_human_reviews_decided_by_user", type_="foreignkey")
        batch.drop_column("decided_by_user_id")
    with op.batch_alter_table("user_accounts") as batch:
        batch.drop_constraint("uq_user_accounts_bootstrap_slot", type_="unique")
        batch.drop_constraint("ck_user_accounts_bootstrap_slot", type_="check")
        batch.drop_column("bootstrap_slot")
