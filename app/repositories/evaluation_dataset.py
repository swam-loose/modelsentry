from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.evaluation_dataset import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationDatasetVersion,
)
from app.schemas.evaluation_dataset import (
    EvaluationDatasetCreate,
    EvaluationDatasetVersionCreate,
)


class EvaluationDatasetRepository:
    """Persist dataset metadata, versions, and ordered evaluation cases."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_dataset(self, payload: EvaluationDatasetCreate) -> EvaluationDataset:
        dataset = EvaluationDataset(**payload.model_dump())
        self.session.add(dataset)
        self._commit()
        self.session.refresh(dataset)
        return dataset

    def create_version(
        self,
        dataset_id: UUID,
        payload: EvaluationDatasetVersionCreate,
        content_sha256: str,
    ) -> EvaluationDatasetVersion:
        dataset_version = EvaluationDatasetVersion(
            dataset_id=dataset_id,
            version=self.get_latest_version_number(dataset_id) + 1,
            content_sha256=content_sha256,
            case_count=len(payload.cases),
            change_note=payload.change_note,
        )
        dataset_version.cases = [
            EvaluationCase(
                position=position,
                case_key=case.case_key,
                input_data=case.input,
                expected_output=case.expected_output,
                case_metadata=case.metadata,
            )
            for position, case in enumerate(payload.cases)
        ]
        self.session.add(dataset_version)
        self._commit()
        self.session.refresh(dataset_version)
        return dataset_version

    def get_by_id(self, dataset_id: UUID) -> EvaluationDataset | None:
        statement = (
            select(EvaluationDataset)
            .where(EvaluationDataset.id == dataset_id)
            .options(selectinload(EvaluationDataset.versions))
        )
        return self.session.scalar(statement)

    def get_by_slug(self, slug: str) -> EvaluationDataset | None:
        statement = select(EvaluationDataset).where(EvaluationDataset.slug == slug)
        return self.session.scalar(statement)

    def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[EvaluationDataset]:
        statement = (
            select(EvaluationDataset)
            .order_by(EvaluationDataset.created_at, EvaluationDataset.id)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def list_versions(self, dataset_id: UUID) -> list[EvaluationDatasetVersion]:
        statement = (
            select(EvaluationDatasetVersion)
            .where(EvaluationDatasetVersion.dataset_id == dataset_id)
            .order_by(EvaluationDatasetVersion.version)
        )
        return list(self.session.scalars(statement))

    def get_version(
        self,
        dataset_id: UUID,
        version: int,
    ) -> EvaluationDatasetVersion | None:
        statement = (
            select(EvaluationDatasetVersion)
            .where(
                EvaluationDatasetVersion.dataset_id == dataset_id,
                EvaluationDatasetVersion.version == version,
            )
            .options(selectinload(EvaluationDatasetVersion.cases))
        )
        return self.session.scalar(statement)

    def get_version_by_hash(
        self,
        dataset_id: UUID,
        content_sha256: str,
    ) -> EvaluationDatasetVersion | None:
        statement = select(EvaluationDatasetVersion).where(
            EvaluationDatasetVersion.dataset_id == dataset_id,
            EvaluationDatasetVersion.content_sha256 == content_sha256,
        )
        return self.session.scalar(statement)

    def get_latest_version_number(self, dataset_id: UUID) -> int:
        statement = select(func.max(EvaluationDatasetVersion.version)).where(
            EvaluationDatasetVersion.dataset_id == dataset_id
        )
        return self.session.scalar(statement) or 0

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
