from uuid import uuid4

from app.models.evaluation_run import EvaluationRun
from app.models.human_review import HumanReview


def make_run() -> EvaluationRun:
    return EvaluationRun(
        registered_model_id=uuid4(),
        prompt_version_id=uuid4(),
        dataset_version_id=uuid4(),
        provider="mock",
        model_identifier="deterministic-v1",
        status="completed",
    )


def test_human_review_model_metadata() -> None:
    assert HumanReview.__tablename__ == "human_reviews"
    assert set(HumanReview.__table__.columns.keys()) == {
        "id",
        "run_id",
        "reviewer",
        "reviewer_role",
        "status",
        "rationale",
        "created_at",
        "decided_at",
        "decided_by_user_id",
    }


def test_run_approval_status_is_conservative() -> None:
    run = make_run()
    assert run.approval_status == "not_requested"

    run.reviews = [HumanReview(reviewer="reviewer-a", status="pending")]
    assert run.approval_status == "pending"

    run.reviews[0].status = "approved"
    assert run.approval_status == "approved"

    run.reviews.append(HumanReview(reviewer="reviewer-b", status="rejected"))
    assert run.approval_status == "rejected"
