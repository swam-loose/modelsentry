from sqlalchemy.orm import Session

from app.repositories.evaluation_dataset import EvaluationDatasetRepository
from app.schemas.evaluation_dataset import (
    EvaluationCaseCreate,
    EvaluationDatasetCreate,
    EvaluationDatasetVersionCreate,
)


def test_repository_persists_dataset_version_and_ordered_cases(
    db_session: Session,
) -> None:
    repository = EvaluationDatasetRepository(db_session)
    dataset = repository.create_dataset(
        EvaluationDatasetCreate(
            name="Geography QA",
            slug="geography-qa",
        )
    )
    payload = EvaluationDatasetVersionCreate(
        cases=[
            EvaluationCaseCreate(
                case_key="capital-france",
                input={"question": "What is the capital of France?"},
                expected_output={"contains": "Paris"},
            ),
            EvaluationCaseCreate(
                case_key="capital-brazil",
                input={"question": "What is the capital of Brazil?"},
                expected_output={"contains": "Brasilia"},
            ),
        ],
        change_note="Initial synthetic cases.",
    )

    version = repository.create_version(dataset.id, payload, "a" * 64)

    assert repository.get_by_slug("geography-qa") is dataset
    assert repository.get_by_id(dataset.id) is dataset
    assert version.version == 1
    assert version.case_count == 2
    assert [case.position for case in version.cases] == [0, 1]
    assert [case.case_key for case in version.cases] == [
        "capital-france",
        "capital-brazil",
    ]
    assert repository.get_version(dataset.id, 1) is version
    assert repository.get_version_by_hash(dataset.id, "a" * 64) is version
