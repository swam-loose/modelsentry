import pytest
from pydantic import ValidationError

from app.schemas.human_review import HumanReviewCreate, HumanReviewDecision


def test_review_create_normalizes_reviewer_identifier() -> None:
    payload = HumanReviewCreate(
        run_id="00000000-0000-0000-0000-000000000001",
        reviewer="  QA.Lead@Example.com  ",
        reviewer_role="  release manager  ",
    )

    assert payload.reviewer == "qa.lead@example.com"
    assert payload.reviewer_role == "release manager"


def test_approval_can_include_optional_rationale() -> None:
    payload = HumanReviewDecision(
        decision="approved",
        rationale="Evidence and deterministic checks were reviewed.",
    )

    assert payload.decision == "approved"


def test_rejection_requires_rationale() -> None:
    with pytest.raises(ValidationError, match="rationale is required"):
        HumanReviewDecision(decision="rejected")


@pytest.mark.parametrize("decision", ["pending", "escalated"])
def test_decision_rejects_non_final_status(decision: str) -> None:
    with pytest.raises(ValidationError):
        HumanReviewDecision(decision=decision)
