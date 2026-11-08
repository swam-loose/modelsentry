from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.evaluation_run import EvaluationRun
from app.repositories.human_review import HumanReviewRepository
from app.schemas.human_review import HumanReviewCreate, HumanReviewDecision


def create_completed_run(db_session: Session) -> EvaluationRun:
    run = EvaluationRun(
        registered_model_id=uuid4(),
        prompt_version_id=uuid4(),
        dataset_version_id=uuid4(),
        provider="mock",
        model_identifier="deterministic-v1",
        status="completed",
        total_cases=1,
        succeeded_cases=1,
        passed_cases=1,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def test_repository_persists_assignment_filters_and_decision(
    db_session: Session,
) -> None:
    run = create_completed_run(db_session)
    repository = HumanReviewRepository(db_session)
    review = repository.create(
        HumanReviewCreate(
            run_id=run.id,
            reviewer="qa.lead@example.com",
            reviewer_role="release-manager",
        )
    )

    assert review.status == "pending"
    assert repository.get_by_id(review.id) is review
    assert repository.get_by_run_and_reviewer(run.id, review.reviewer) is review
    assert repository.list_all(status="pending") == [review]

    decided = repository.decide(
        review,
        HumanReviewDecision(
            decision="approved",
            rationale="All evidence was reviewed.",
        ),
    )

    assert decided.status == "approved"
    assert decided.decided_at is not None
    assert repository.list_all(reviewer="qa.lead@example.com") == [review]
