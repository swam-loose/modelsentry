from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EvaluationDataset(Base):
    """A named collection of reproducible evaluation cases."""

    __tablename__ = "evaluation_datasets"

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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    versions: Mapped[list[EvaluationDatasetVersion]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="EvaluationDatasetVersion.version",
    )


class EvaluationDatasetVersion(Base):
    """An immutable snapshot of an evaluation dataset."""

    __tablename__ = "evaluation_dataset_versions"
    __table_args__ = (
        CheckConstraint(
            "version > 0",
            name="ck_evaluation_dataset_versions_positive_version",
        ),
        CheckConstraint(
            "case_count > 0",
            name="ck_evaluation_dataset_versions_positive_case_count",
        ),
        UniqueConstraint(
            "dataset_id",
            "version",
            name="uq_evaluation_dataset_versions_dataset_version",
        ),
        UniqueConstraint(
            "dataset_id",
            "content_sha256",
            name="uq_evaluation_dataset_versions_dataset_hash",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    dataset: Mapped[EvaluationDataset] = relationship(back_populates="versions")
    cases: Mapped[list[EvaluationCase]] = relationship(
        back_populates="dataset_version",
        cascade="all, delete-orphan",
        order_by="EvaluationCase.position",
    )


class EvaluationCase(Base):
    """One ordered input and expected-output record in a dataset version."""

    __tablename__ = "evaluation_cases"
    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_evaluation_cases_nonnegative_position",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "case_key",
            name="uq_evaluation_cases_version_key",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "position",
            name="uq_evaluation_cases_version_position",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    dataset_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    case_key: Mapped[str] = mapped_column(String(120), nullable=False)
    input_data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    expected_output: Mapped[object | None] = mapped_column(JSON, nullable=True)
    case_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    dataset_version: Mapped[EvaluationDatasetVersion] = relationship(
        back_populates="cases"
    )
