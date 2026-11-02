from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.human_review import HumanReview
from app.repositories.human_review import HumanReviewRepository
from app.schemas.human_review import (
    HumanReviewCreate,
    HumanReviewDecision,
    HumanReviewStatus,
)


class HumanReviewNotFoundError(Exception):
    """Raised when a review or evaluation run does not exist."""


class HumanReviewConflictError(Exception):
    """Raised when a review assignment or transition conflicts with history."""


class HumanReviewService:
    """Enforce supervised, immutable human approval decisions."""

    def __init__(self, session: Session) -> None:
        self.repository = HumanReviewRepository(session)

    def request_review(self, payload: HumanReviewCreate) -> HumanReview:
        run = self.repository.get_run(payload.run_id)
        if run is None:
            raise HumanReviewNotFoundError(
                f"Evaluation run '{payload.run_id}' was not found."
            )
        if run.status != "completed":
            raise HumanReviewConflictError(
                "Human review can only be requested for a completed run."
            )
        existing = self.repository.get_by_run_and_reviewer(
            payload.run_id,
            payload.reviewer,
        )
        if existing is not None:
            raise HumanReviewConflictError(
                f"Reviewer '{payload.reviewer}' is already assigned to this run."
            )
        try:
            return self.repository.create(payload)
        except IntegrityError as error:
            self.repository.session.rollback()
            raise HumanReviewConflictError(
                "The review assignment conflicts with existing review history."
            ) from error

    def get_review(self, review_id: UUID) -> HumanReview:
        review = self.repository.get_by_id(review_id)
        if review is None:
            raise HumanReviewNotFoundError(f"Human review '{review_id}' was not found.")
        return review

    def list_reviews(
        self,
        *,
        run_id: UUID | None = None,
        reviewer: str | None = None,
        status: HumanReviewStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[HumanReview]:
        normalized_reviewer = reviewer.strip().casefold() if reviewer else None
        return self.repository.list_all(
            run_id=run_id,
            reviewer=normalized_reviewer,
            status=status,
            offset=offset,
            limit=limit,
        )

    def decide_review(
        self,
        review_id: UUID,
        payload: HumanReviewDecision,
    ) -> HumanReview:
        review = self.get_review(review_id)
        if review.status != "pending":
            raise HumanReviewConflictError(
                "A completed human review decision is immutable."
            )
        return self.repository.decide(review, payload)
