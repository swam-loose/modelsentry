import pytest
from pydantic import ValidationError

from app.schemas.model import RegisteredModelCreate


def test_model_create_accepts_and_normalizes_valid_data() -> None:
    payload = RegisteredModelCreate(
        name="  Mock Evaluator  ",
        slug="mock-evaluator",
        model_identifier="  deterministic-v1  ",
    )

    assert payload.name == "Mock Evaluator"
    assert payload.provider == "mock"
    assert payload.model_identifier == "deterministic-v1"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("slug", "Invalid Slug"),
        ("provider", "unknown"),
        ("model_identifier", ""),
    ],
)
def test_model_create_rejects_invalid_data(field: str, value: str) -> None:
    data = {
        "name": "Mock Evaluator",
        "slug": "mock-evaluator",
        "provider": "mock",
        "model_identifier": "deterministic-v1",
    }
    data[field] = value

    with pytest.raises(ValidationError):
        RegisteredModelCreate.model_validate(data)
