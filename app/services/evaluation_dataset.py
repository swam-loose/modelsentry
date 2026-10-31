import json
from hashlib import sha256
from json import JSONDecodeError
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.evaluation_dataset import (
    EvaluationDataset,
    EvaluationDatasetVersion,
)
from app.repositories.evaluation_dataset import EvaluationDatasetRepository
from app.schemas.evaluation_dataset import (
    EvaluationCaseCreate,
    EvaluationDatasetCreate,
    EvaluationDatasetVersionCreate,
)

MAX_JSONL_BYTES = 2_000_000


class DatasetRegistryConflictError(Exception):
    """Raised when dataset registry uniqueness is violated."""


class DatasetRegistryNotFoundError(Exception):
    """Raised when a requested dataset or version does not exist."""


class DatasetValidationError(Exception):
    """Raised when supplied JSONL cannot become a valid dataset version."""


class DatasetContentTooLargeError(DatasetValidationError):
    """Raised when JSONL exceeds the local ingestion limit."""


class DatasetRegistryService:
    """Apply dataset validation and deterministic versioning rules."""

    def __init__(self, session: Session) -> None:
        self.repository = EvaluationDatasetRepository(session)

    def create_dataset(
        self,
        payload: EvaluationDatasetCreate,
    ) -> EvaluationDataset:
        if self.repository.get_by_slug(payload.slug) is not None:
            raise DatasetRegistryConflictError(
                f"A dataset with slug '{payload.slug}' is already registered."
            )
        try:
            return self.repository.create_dataset(payload)
        except IntegrityError as error:
            raise DatasetRegistryConflictError(
                "The dataset conflicts with an existing registry entry."
            ) from error

    def get_dataset(self, dataset_id: UUID) -> EvaluationDataset:
        dataset = self.repository.get_by_id(dataset_id)
        if dataset is None:
            raise DatasetRegistryNotFoundError(
                f"Evaluation dataset '{dataset_id}' was not found."
            )
        return dataset

    def list_datasets(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[EvaluationDataset]:
        return self.repository.list_all(offset=offset, limit=limit)

    def create_version(
        self,
        dataset_id: UUID,
        payload: EvaluationDatasetVersionCreate,
    ) -> EvaluationDatasetVersion:
        self.get_dataset(dataset_id)
        content_sha256 = self._content_sha256(payload.cases)
        if self.repository.get_version_by_hash(dataset_id, content_sha256) is not None:
            raise DatasetRegistryConflictError(
                "An identical dataset version is already registered."
            )
        try:
            return self.repository.create_version(
                dataset_id,
                payload,
                content_sha256,
            )
        except IntegrityError as error:
            raise DatasetRegistryConflictError(
                "The dataset version conflicts with an existing version."
            ) from error

    def create_version_from_jsonl(
        self,
        dataset_id: UUID,
        content: bytes,
        *,
        change_note: str | None = None,
    ) -> EvaluationDatasetVersion:
        payload = self.parse_jsonl(content, change_note=change_note)
        return self.create_version(dataset_id, payload)

    def list_versions(self, dataset_id: UUID) -> list[EvaluationDatasetVersion]:
        self.get_dataset(dataset_id)
        return self.repository.list_versions(dataset_id)

    def get_version(
        self,
        dataset_id: UUID,
        version: int,
    ) -> EvaluationDatasetVersion:
        self.get_dataset(dataset_id)
        dataset_version = self.repository.get_version(dataset_id, version)
        if dataset_version is None:
            raise DatasetRegistryNotFoundError(
                f"Version {version} of dataset '{dataset_id}' was not found."
            )
        return dataset_version

    @staticmethod
    def parse_jsonl(
        content: bytes,
        *,
        change_note: str | None = None,
    ) -> EvaluationDatasetVersionCreate:
        if len(content) > MAX_JSONL_BYTES:
            raise DatasetContentTooLargeError(
                f"JSONL content exceeds the {MAX_JSONL_BYTES}-byte limit."
            )
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DatasetValidationError("JSONL content must use UTF-8.") from error

        cases: list[EvaluationCaseCreate] = []
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except JSONDecodeError as error:
                raise DatasetValidationError(
                    f"Line {line_number} is not valid JSON."
                ) from error
            if not isinstance(value, dict):
                raise DatasetValidationError(
                    f"Line {line_number} must contain a JSON object."
                )
            try:
                cases.append(EvaluationCaseCreate.model_validate(value))
            except ValidationError as error:
                raise DatasetValidationError(
                    f"Line {line_number} is not a valid evaluation case."
                ) from error

        try:
            return EvaluationDatasetVersionCreate(
                cases=cases,
                change_note=change_note,
            )
        except ValidationError as error:
            raise DatasetValidationError(
                "JSONL must contain at least one case with unique case keys."
            ) from error

    @staticmethod
    def _content_sha256(cases: list[EvaluationCaseCreate]) -> str:
        canonical_lines = [
            json.dumps(
                case.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for case in cases
        ]
        canonical_content = ("\n".join(canonical_lines) + "\n").encode()
        return sha256(canonical_content).hexdigest()
