from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.evaluation_dataset import (
    EvaluationDatasetCreate,
    EvaluationDatasetDetailRead,
    EvaluationDatasetRead,
    EvaluationDatasetVersionCreate,
    EvaluationDatasetVersionDetailRead,
    EvaluationDatasetVersionRead,
)
from app.services.evaluation_dataset import (
    DatasetContentTooLargeError,
    DatasetRegistryConflictError,
    DatasetRegistryNotFoundError,
    DatasetRegistryService,
    DatasetValidationError,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "",
    response_model=EvaluationDatasetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dataset(
    payload: EvaluationDatasetCreate,
    session: DbSession,
) -> EvaluationDatasetRead:
    """Register evaluation dataset metadata."""

    try:
        dataset = DatasetRegistryService(session).create_dataset(payload)
    except DatasetRegistryConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return EvaluationDatasetRead.model_validate(dataset)


@router.get("", response_model=list[EvaluationDatasetRead])
def list_datasets(
    session: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[EvaluationDatasetRead]:
    """List evaluation datasets in deterministic creation order."""

    datasets = DatasetRegistryService(session).list_datasets(
        offset=offset,
        limit=limit,
    )
    return [EvaluationDatasetRead.model_validate(dataset) for dataset in datasets]


@router.get("/{dataset_id}", response_model=EvaluationDatasetDetailRead)
def get_dataset(
    dataset_id: UUID,
    session: DbSession,
) -> EvaluationDatasetDetailRead:
    """Return dataset metadata and its immutable version history."""

    try:
        dataset = DatasetRegistryService(session).get_dataset(dataset_id)
    except DatasetRegistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return EvaluationDatasetDetailRead.model_validate(dataset)


@router.post(
    "/{dataset_id}/versions",
    response_model=EvaluationDatasetVersionDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dataset_version(
    dataset_id: UUID,
    payload: EvaluationDatasetVersionCreate,
    session: DbSession,
) -> EvaluationDatasetVersionDetailRead:
    """Create an immutable dataset version from structured JSON."""

    service = DatasetRegistryService(session)
    try:
        dataset_version = service.create_version(dataset_id, payload)
    except DatasetRegistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DatasetRegistryConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return EvaluationDatasetVersionDetailRead.model_validate(dataset_version)


@router.post(
    "/{dataset_id}/versions/jsonl",
    response_model=EvaluationDatasetVersionDetailRead,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/x-ndjson": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        }
    },
)
async def create_dataset_version_from_jsonl(
    dataset_id: UUID,
    request: Request,
    session: DbSession,
    change_note: Annotated[str | None, Query(max_length=500)] = None,
) -> EvaluationDatasetVersionDetailRead:
    """Create an immutable dataset version from UTF-8 JSON Lines."""

    content = await request.body()
    service = DatasetRegistryService(session)
    try:
        dataset_version = service.create_version_from_jsonl(
            dataset_id,
            content,
            change_note=change_note,
        )
    except DatasetContentTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(error),
        ) from error
    except DatasetValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except DatasetRegistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DatasetRegistryConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return EvaluationDatasetVersionDetailRead.model_validate(dataset_version)


@router.get(
    "/{dataset_id}/versions",
    response_model=list[EvaluationDatasetVersionRead],
)
def list_dataset_versions(
    dataset_id: UUID,
    session: DbSession,
) -> list[EvaluationDatasetVersionRead]:
    """List every immutable version of an evaluation dataset."""

    try:
        versions = DatasetRegistryService(session).list_versions(dataset_id)
    except DatasetRegistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return [
        EvaluationDatasetVersionRead.model_validate(version) for version in versions
    ]


@router.get(
    "/{dataset_id}/versions/{version}",
    response_model=EvaluationDatasetVersionDetailRead,
)
def get_dataset_version(
    dataset_id: UUID,
    version: Annotated[int, Path(ge=1)],
    session: DbSession,
) -> EvaluationDatasetVersionDetailRead:
    """Return one exact dataset version and its ordered evaluation cases."""

    try:
        dataset_version = DatasetRegistryService(session).get_version(
            dataset_id,
            version,
        )
    except DatasetRegistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return EvaluationDatasetVersionDetailRead.model_validate(dataset_version)
