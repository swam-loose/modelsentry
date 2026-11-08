from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.schemas.evaluation_dataset import (
    EvaluationCaseCreate,
    EvaluationDatasetCreate,
    EvaluationDatasetVersionCreate,
)
from app.services.evaluation_dataset import (
    MAX_JSONL_BYTES,
    DatasetContentTooLargeError,
    DatasetRegistryConflictError,
    DatasetRegistryNotFoundError,
    DatasetRegistryService,
    DatasetValidationError,
)


def create_dataset(service: DatasetRegistryService):
    return service.create_dataset(
        EvaluationDatasetCreate(
            name="Geography QA",
            slug="geography-qa",
        )
    )


def make_version() -> EvaluationDatasetVersionCreate:
    return EvaluationDatasetVersionCreate(
        cases=[
            EvaluationCaseCreate(
                case_key="capital-france",
                input={"question": "What is the capital of France?"},
                expected_output={"contains": "Paris"},
            )
        ]
    )


def test_service_parses_jsonl_and_creates_version(db_session: Session) -> None:
    service = DatasetRegistryService(db_session)
    dataset = create_dataset(service)
    content = (
        b'{"case_key":"capital-france","input":{"question":"Capital of France?"},'
        b'"expected_output":{"contains":"Paris"}}\n'
        b'{"case_key":"capital-brazil","input":{"question":"Capital of Brazil?"},'
        b'"expected_output":{"contains":"Brasilia"}}\n'
    )

    version = service.create_version_from_jsonl(
        dataset.id,
        content,
        change_note="Initial JSONL import.",
    )

    assert version.version == 1
    assert version.case_count == 2
    assert version.change_note == "Initial JSONL import."
    assert len(version.content_sha256) == 64
    assert service.get_version(dataset.id, 1) is version


def test_service_rejects_semantically_identical_version(db_session: Session) -> None:
    service = DatasetRegistryService(db_session)
    dataset = create_dataset(service)
    service.create_version(dataset.id, make_version())

    with pytest.raises(DatasetRegistryConflictError):
        service.create_version(dataset.id, make_version())


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not-json\n", "Line 1"),
        (b"[]\n", "Line 1"),
        (b"", "at least one"),
        (
            b'{"case_key":"same","input":{}}\n{"case_key":"same","input":{}}\n',
            "unique",
        ),
    ],
)
def test_service_rejects_invalid_jsonl(content: bytes, message: str) -> None:
    with pytest.raises(DatasetValidationError, match=message):
        DatasetRegistryService.parse_jsonl(content)


def test_service_rejects_oversized_jsonl() -> None:
    with pytest.raises(DatasetContentTooLargeError):
        DatasetRegistryService.parse_jsonl(b"x" * (MAX_JSONL_BYTES + 1))


def test_service_reports_missing_dataset(db_session: Session) -> None:
    service = DatasetRegistryService(db_session)
    unknown_id = UUID("00000000-0000-0000-0000-000000000000")

    with pytest.raises(DatasetRegistryNotFoundError):
        service.get_dataset(unknown_id)
