from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegisteredModel(Base):
    """A model endpoint available for reproducible evaluation runs."""

    __tablename__ = "registered_models"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('mock', 'ollama')",
            name="ck_registered_models_provider",
        ),
        UniqueConstraint(
            "provider",
            "model_identifier",
            name="uq_registered_models_provider_identifier",
        ),
        CheckConstraint(
            "input_cost_per_million >= 0",
            name="ck_registered_models_nonnegative_input_cost",
        ),
        CheckConstraint(
            "output_cost_per_million >= 0",
            name="ck_registered_models_nonnegative_output_cost",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="mock",
        server_default="mock",
    )
    model_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_cost_per_million: Mapped[Decimal] = mapped_column(
        Numeric(14, 6),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    output_cost_per_million: Mapped[Decimal] = mapped_column(
        Numeric(14, 6),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )
