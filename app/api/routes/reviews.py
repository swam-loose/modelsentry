from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.security import CurrentPrincipal, get_current_principal
from app.db.session import get_db_session
from app.schemas.human_review import (
    HumanReviewCreate,
    HumanReviewDecision,
    HumanReviewRead,
    HumanReviewStatus,
)
from app.services.human_review import (
    HumanReviewConflictError,
    HumanReviewForbiddenError,
    HumanReviewNotFoundError,
    HumanReviewService,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "",
    response_model=HumanReviewRead,
    status_code=status.HTTP_201_CREATED,
)
def request_human_review(
    payload: HumanReviewCreate,
    session: DbSession,
) -> HumanReviewRead:
    """Assign a human reviewer to one completed evaluation run."""

    try:
        review = HumanReviewService(session).request_review(payload)
    except HumanReviewNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except HumanReviewConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return HumanReviewRead.model_validate(review)


@router.get("", response_model=list[HumanReviewRead])
def list_human_reviews(
    session: DbSession,
    run_id: UUID | None = None,
    reviewer: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    review_status: Annotated[
        HumanReviewStatus | None,
        Query(alias="status"),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[HumanReviewRead]:
    """List the human review queue with optional deterministic filters."""

    reviews = HumanReviewService(session).list_reviews(
        run_id=run_id,
        reviewer=reviewer,
        status=review_status,
        offset=offset,
        limit=limit,
    )
    return [HumanReviewRead.model_validate(review) for review in reviews]


@router.get("/{review_id}", response_model=HumanReviewRead)
def get_human_review(
    review_id: UUID,
    session: DbSession,
) -> HumanReviewRead:
    """Return one review assignment and its final decision, when available."""

    try:
        review = HumanReviewService(session).get_review(review_id)
    except HumanReviewNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return HumanReviewRead.model_validate(review)


@router.patch("/{review_id}", response_model=HumanReviewRead)
def decide_human_review(
    review_id: UUID,
    payload: HumanReviewDecision,
    session: DbSession,
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> HumanReviewRead:
    """Record one final human approval or rejection decision."""

    try:
        review = HumanReviewService(session).decide_review(
            review_id,
            payload,
            actor_user_id=principal.user.id,
            actor_email=principal.user.email,
            actor_role=principal.user.role,
        )
    except HumanReviewNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except HumanReviewConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except HumanReviewForbiddenError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    return HumanReviewRead.model_validate(review)
