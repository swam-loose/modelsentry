from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.model import RegisteredModelCreate, RegisteredModelRead
from app.services.model_registry import (
    ModelRegistryConflictError,
    ModelRegistryNotFoundError,
    ModelRegistryService,
)

router = APIRouter(prefix="/models", tags=["models"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "",
    response_model=RegisteredModelRead,
    status_code=status.HTTP_201_CREATED,
)
def create_model(
    payload: RegisteredModelCreate,
    session: DbSession,
) -> RegisteredModelRead:
    """Register a model endpoint without storing provider credentials."""

    service = ModelRegistryService(session)
    try:
        return RegisteredModelRead.model_validate(service.create(payload))
    except ModelRegistryConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get("", response_model=list[RegisteredModelRead])
def list_models(
    session: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[RegisteredModelRead]:
    """List registered models in deterministic creation order."""

    models = ModelRegistryService(session).list_models(offset=offset, limit=limit)
    return [RegisteredModelRead.model_validate(model) for model in models]


@router.get("/{model_id}", response_model=RegisteredModelRead)
def get_model(model_id: UUID, session: DbSession) -> RegisteredModelRead:
    """Return one registered model by its immutable identifier."""

    try:
        model = ModelRegistryService(session).get_model(model_id)
    except ModelRegistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return RegisteredModelRead.model_validate(model)
