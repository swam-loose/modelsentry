from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.release_gate import (
    ReleaseGateCreate,
    ReleaseGateDetailRead,
    ReleaseGateEvaluationCreate,
    ReleaseGateEvaluationRead,
    ReleaseGateRead,
    ReleaseGateVersionCreate,
    ReleaseGateVersionRead,
)
from app.services.release_gate import (
    ReleaseGateConflictError,
    ReleaseGateNotFoundError,
    ReleaseGateService,
)

router = APIRouter(prefix="/release-gates", tags=["release-gates"])
evaluation_router = APIRouter(
    prefix="/release-gate-evaluations",
    tags=["release-gates"],
)
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "",
    response_model=ReleaseGateDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def create_release_gate(
    payload: ReleaseGateCreate,
    session: DbSession,
) -> ReleaseGateDetailRead:
    """Create release-gate metadata and immutable policy version one."""

    try:
        gate = ReleaseGateService(session).create_gate(payload)
    except ReleaseGateConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return ReleaseGateDetailRead.model_validate(gate)


@router.get("", response_model=list[ReleaseGateRead])
def list_release_gates(
    session: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ReleaseGateRead]:
    """List release-gate registry metadata."""

    gates = ReleaseGateService(session).list_gates(offset=offset, limit=limit)
    return [ReleaseGateRead.model_validate(gate) for gate in gates]


@router.get("/{gate_id}", response_model=ReleaseGateDetailRead)
def get_release_gate(
    gate_id: UUID,
    session: DbSession,
) -> ReleaseGateDetailRead:
    """Return a release gate and its complete policy-version history."""

    try:
        gate = ReleaseGateService(session).get_gate(gate_id)
    except ReleaseGateNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return ReleaseGateDetailRead.model_validate(gate)


@router.post(
    "/{gate_id}/versions",
    response_model=ReleaseGateVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_release_gate_version(
    gate_id: UUID,
    payload: ReleaseGateVersionCreate,
    session: DbSession,
) -> ReleaseGateVersionRead:
    """Append an immutable release-gate policy version."""

    try:
        version = ReleaseGateService(session).create_version(gate_id, payload)
    except ReleaseGateNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ReleaseGateConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return ReleaseGateVersionRead.model_validate(version)


@router.post(
    "/{gate_id}/evaluations",
    response_model=ReleaseGateEvaluationRead,
    status_code=status.HTTP_201_CREATED,
)
def evaluate_release_gate(
    gate_id: UUID,
    payload: ReleaseGateEvaluationCreate,
    session: DbSession,
) -> ReleaseGateEvaluationRead:
    """Persist an evidence-backed decision using the latest gate version."""

    try:
        evaluation = ReleaseGateService(session).evaluate(gate_id, payload)
    except ReleaseGateNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ReleaseGateConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return ReleaseGateEvaluationRead.model_validate(evaluation)


@router.get(
    "/{gate_id}/evaluations",
    response_model=list[ReleaseGateEvaluationRead],
)
def list_release_gate_evaluations(
    gate_id: UUID,
    session: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ReleaseGateEvaluationRead]:
    """List immutable decisions made with every version of one gate."""

    try:
        evaluations = ReleaseGateService(session).list_evaluations(
            gate_id,
            offset=offset,
            limit=limit,
        )
    except ReleaseGateNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return [
        ReleaseGateEvaluationRead.model_validate(evaluation)
        for evaluation in evaluations
    ]


@evaluation_router.get(
    "/{evaluation_id}",
    response_model=ReleaseGateEvaluationRead,
)
def get_release_gate_evaluation(
    evaluation_id: UUID,
    session: DbSession,
) -> ReleaseGateEvaluationRead:
    """Return one immutable gate decision and all supporting evidence."""

    try:
        evaluation = ReleaseGateService(session).get_evaluation(evaluation_id)
    except ReleaseGateNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return ReleaseGateEvaluationRead.model_validate(evaluation)
