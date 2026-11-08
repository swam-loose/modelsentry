from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.evaluation_run import (
    EvaluationRunCreate,
    EvaluationRunDetailRead,
    EvaluationRunRead,
)
from app.services.evaluation_run import (
    EvaluationRunNotFoundError,
    EvaluationRunService,
    EvaluationRunUnsupportedProviderError,
)

router = APIRouter(prefix="/runs", tags=["runs"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "",
    response_model=EvaluationRunDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def create_evaluation_run(
    payload: EvaluationRunCreate,
    session: DbSession,
) -> EvaluationRunDetailRead:
    """Execute a deterministic mock-provider run synchronously."""

    try:
        run = EvaluationRunService(session).create_and_execute(payload)
    except EvaluationRunNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except EvaluationRunUnsupportedProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    return EvaluationRunDetailRead.model_validate(run)


@router.get("", response_model=list[EvaluationRunRead])
def list_evaluation_runs(
    session: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[EvaluationRunRead]:
    """List evaluation runs in deterministic creation order."""

    runs = EvaluationRunService(session).list_runs(offset=offset, limit=limit)
    return [EvaluationRunRead.model_validate(run) for run in runs]


@router.get("/{run_id}", response_model=EvaluationRunDetailRead)
def get_evaluation_run(
    run_id: UUID,
    session: DbSession,
) -> EvaluationRunDetailRead:
    """Return one evaluation run and all case-level evidence."""

    try:
        run = EvaluationRunService(session).get_run(run_id)
    except EvaluationRunNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return EvaluationRunDetailRead.model_validate(run)
