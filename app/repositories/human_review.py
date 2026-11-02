from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.evaluation_run import EvaluationRun
from app.models.human_review import HumanReview
from app.schemas.human_review import HumanReviewCreate, HumanReviewDecision


class HumanReviewRepository:
    """Persist review assignments and final decisions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_run(self, run_id: UUID) -> EvaluationRun | None:
        statement = (
            select(EvaluationRun)
            .where(EvaluationRun.id == run_id)
            .options(selectinload(EvaluationRun.reviews))
        )
        return self.session.scalar(statement)

    def create(self, payload: HumanReviewCreate) -> HumanReview:
        review = HumanReview(**payload.model_dump())
        self.session.add(review)
        self.session.commit()
        self.session.refresh(review)
        return review

    def get_by_id(self, review_id: UUID) -> HumanReview | None:
        return self.session.get(HumanReview, review_id)

    def get_by_run_and_reviewer(
        self,
        run_id: UUID,
        reviewer: str,
    ) -> HumanReview | None:
        statement = select(HumanReview).where(
            HumanReview.run_id == run_id,
            HumanReview.reviewer == reviewer,
        )
        return self.session.scalar(statement)

    def list_all(
        self,
        *,
        run_id: UUID | None = None,
        reviewer: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[HumanReview]:
        statement = select(HumanReview)
        if run_id is not None:
            statement = statement.where(HumanReview.run_id == run_id)
        if reviewer is not None:
            statement = statement.where(HumanReview.reviewer == reviewer)
        if status is not None:
            statement = statement.where(HumanReview.status == status)
        statement = (
            statement.order_by(HumanReview.created_at, HumanReview.id)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def decide(
        self,
        review: HumanReview,
        payload: HumanReviewDecision,
    ) -> HumanReview:
        review.status = payload.decision
        review.rationale = payload.rationale
        review.decided_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(review)
        return review
