from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.evaluation_run import EvaluationRun
from app.schemas.human_review import HumanReviewCreate, HumanReviewDecision
from app.services.human_review import (
    HumanReviewConflictError,
    HumanReviewNotFoundError,
    HumanReviewService,
)


def create_run(db_session: Session, *, status: str = "completed") -> EvaluationRun:
    run = EvaluationRun(
        registered_model_id=uuid4(),
        prompt_version_id=uuid4(),
        dataset_version_id=uuid4(),
        provider="mock",
        model_identifier="deterministic-v1",
        status=status,
        total_cases=1,
        succeeded_cases=1 if status == "completed" else 0,
        passed_cases=1 if status == "completed" else 0,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def test_service_requests_and_approves_review(db_session: Session) -> None:
    run = create_run(db_session)
    service = HumanReviewService(db_session)
    review = service.request_review(
        HumanReviewCreate(
            run_id=run.id,
            reviewer="qa.lead@example.com",
        )
    )

    assert review.status == "pending"
    assert service.list_reviews(reviewer=" QA.LEAD@EXAMPLE.COM ") == [review]

    decided = service.decide_review(
        review.id,
        HumanReviewDecision(decision="approved"),
    )

    assert decided.status == "approved"
    assert decided.decided_at is not None


def test_service_rejects_duplicate_assignment(db_session: Session) -> None:
    run = create_run(db_session)
    service = HumanReviewService(db_session)
    payload = HumanReviewCreate(
        run_id=run.id,
        reviewer="qa.lead@example.com",
    )
    service.request_review(payload)

    with pytest.raises(HumanReviewConflictError, match="already assigned"):
        service.request_review(payload)


def test_service_rejects_review_for_incomplete_run(db_session: Session) -> None:
    run = create_run(db_session, status="running")

    with pytest.raises(HumanReviewConflictError, match="completed run"):
        HumanReviewService(db_session).request_review(
            HumanReviewCreate(
                run_id=run.id,
                reviewer="qa.lead@example.com",
            )
        )


def test_service_prevents_decision_rewrite(db_session: Session) -> None:
    run = create_run(db_session)
    service = HumanReviewService(db_session)
    review = service.request_review(
        HumanReviewCreate(
            run_id=run.id,
            reviewer="qa.lead@example.com",
        )
    )
    service.decide_review(
        review.id,
        HumanReviewDecision(decision="rejected", rationale="Evidence failed review."),
    )

    with pytest.raises(HumanReviewConflictError, match="immutable"):
        service.decide_review(
            review.id,
            HumanReviewDecision(decision="approved"),
        )


def test_service_reports_missing_run_and_review(db_session: Session) -> None:
    service = HumanReviewService(db_session)
    missing_run_id = UUID("00000000-0000-0000-0000-000000000001")
    missing_review_id = UUID("00000000-0000-0000-0000-000000000002")

    with pytest.raises(HumanReviewNotFoundError, match="Evaluation run"):
        service.request_review(
            HumanReviewCreate(
                run_id=missing_run_id,
                reviewer="qa.lead@example.com",
            )
        )
    with pytest.raises(HumanReviewNotFoundError, match="Human review"):
        service.get_review(missing_review_id)
