from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.run_comparison import RunComparisonCreate, RunComparisonRead
from app.services.run_comparison import (
    RunComparisonConflictError,
    RunComparisonNotFoundError,
    RunComparisonService,
)

router = APIRouter(prefix="/run-comparisons", tags=["run-comparisons"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post("", response_model=RunComparisonRead)
def compare_evaluation_runs(
    payload: RunComparisonCreate,
    session: DbSession,
) -> RunComparisonRead:
    """Compare quality, latency, token usage, and estimated cost evidence."""

    try:
        return RunComparisonService(session).compare(payload)
    except RunComparisonNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except RunComparisonConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
