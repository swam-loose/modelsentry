from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.evaluation_run import EvaluationRunCreate


def test_evaluation_run_create_accepts_valid_identifiers() -> None:
    payload = EvaluationRunCreate(
        registered_model_id="00000000-0000-0000-0000-000000000001",
        prompt_version_id="00000000-0000-0000-0000-000000000002",
        dataset_version_id="00000000-0000-0000-0000-000000000003",
    )

    assert payload.registered_model_id == UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.parametrize(
    "field",
    [
        "registered_model_id",
        "prompt_version_id",
        "dataset_version_id",
    ],
)
def test_evaluation_run_create_rejects_invalid_identifier(field: str) -> None:
    data = {
        "registered_model_id": "00000000-0000-0000-0000-000000000001",
        "prompt_version_id": "00000000-0000-0000-0000-000000000002",
        "dataset_version_id": "00000000-0000-0000-0000-000000000003",
    }
    data[field] = "not-a-uuid"

    with pytest.raises(ValidationError):
        EvaluationRunCreate.model_validate(data)
