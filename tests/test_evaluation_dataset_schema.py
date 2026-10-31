import pytest
from pydantic import ValidationError

from app.schemas.evaluation_dataset import (
    EvaluationCaseCreate,
    EvaluationDatasetCreate,
    EvaluationDatasetVersionCreate,
)


def make_case(case_key: str = "capital-france") -> EvaluationCaseCreate:
    return EvaluationCaseCreate(
        case_key=case_key,
        input={"question": "What is the capital of France?"},
        expected_output={"contains": "Paris"},
        metadata={"category": "geography"},
    )


def test_dataset_create_accepts_and_normalizes_valid_data() -> None:
    payload = EvaluationDatasetCreate(
        name="  Geography QA  ",
        slug="geography-qa",
        description="  Synthetic geography questions.  ",
    )

    assert payload.name == "Geography QA"
    assert payload.description == "Synthetic geography questions."


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("slug", "Invalid Slug"),
    ],
)
def test_dataset_create_rejects_invalid_metadata(field: str, value: str) -> None:
    data = {
        "name": "Geography QA",
        "slug": "geography-qa",
    }
    data[field] = value

    with pytest.raises(ValidationError):
        EvaluationDatasetCreate.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_key", "invalid key"),
        ("input", "not-an-object"),
    ],
)
def test_evaluation_case_rejects_invalid_data(field: str, value: object) -> None:
    data: dict[str, object] = {
        "case_key": "capital-france",
        "input": {"question": "What is the capital of France?"},
    }
    data[field] = value

    with pytest.raises(ValidationError):
        EvaluationCaseCreate.model_validate(data)


def test_dataset_version_rejects_duplicate_case_keys() -> None:
    with pytest.raises(ValidationError):
        EvaluationDatasetVersionCreate(
            cases=[make_case(), make_case()],
        )
