from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.schemas.evaluation_dataset import (
    EvaluationCaseCreate,
    EvaluationDatasetCreate,
    EvaluationDatasetVersionCreate,
)
from app.schemas.evaluation_run import EvaluationRunCreate
from app.schemas.model import RegisteredModelCreate
from app.schemas.prompt import PromptCreate, PromptVersionCreate
from app.services.evaluation_dataset import DatasetRegistryService
from app.services.evaluation_run import (
    EvaluationRunNotFoundError,
    EvaluationRunService,
    EvaluationRunUnsupportedProviderError,
)
from app.services.model_registry import ModelRegistryService
from app.services.prompt_registry import PromptRegistryService


def create_dependencies(
    db_session: Session,
    *,
    provider: str = "mock",
    prompt_variables: list[str] | None = None,
) -> EvaluationRunCreate:
    model = ModelRegistryService(db_session).create(
        RegisteredModelCreate(
            name="Mock Evaluator",
            slug=f"{provider}-evaluator",
            provider=provider,
            model_identifier="deterministic-v1",
        )
    )
    variables = ["question"] if prompt_variables is None else prompt_variables
    prompt = PromptRegistryService(db_session).create_prompt(
        PromptCreate(
            name="Geography Answer",
            slug="geography-answer",
            initial_version=PromptVersionCreate(
                system_prompt="Answer from synthetic evidence.",
                user_prompt_template="Question: {{question}}",
                variables=variables,
            ),
        )
    )
    dataset_service = DatasetRegistryService(db_session)
    dataset = dataset_service.create_dataset(
        EvaluationDatasetCreate(
            name="Geography QA",
            slug="geography-qa",
        )
    )
    dataset_version = dataset_service.create_version(
        dataset.id,
        EvaluationDatasetVersionCreate(
            cases=[
                EvaluationCaseCreate(
                    case_key="capital-france",
                    input={
                        "question": "What is the capital of France?",
                        "mock_response": "Paris is the capital of France.",
                    },
                    expected_output={"contains": "Paris"},
                ),
                EvaluationCaseCreate(
                    case_key="capital-brazil",
                    input={
                        "question": "What is the capital of Brazil?",
                        "mock_response": "Brasilia is the capital of Brazil.",
                    },
                    expected_output={"contains": "Brasilia"},
                ),
            ]
        ),
    )
    return EvaluationRunCreate(
        registered_model_id=model.id,
        prompt_version_id=prompt.versions[0].id,
        dataset_version_id=dataset_version.id,
    )


def test_service_executes_deterministic_mock_run(db_session: Session) -> None:
    payload = create_dependencies(db_session)

    run = EvaluationRunService(db_session).create_and_execute(payload)

    assert run.status == "completed"
    assert run.total_cases == 2
    assert run.succeeded_cases == 2
    assert run.errored_cases == 0
    assert [result.output_text for result in run.results] == [
        "Paris is the capital of France.",
        "Brasilia is the capital of Brazil.",
    ]
    assert all(5 <= result.latency_ms <= 50 for result in run.results)


def test_service_records_case_level_rendering_errors(db_session: Session) -> None:
    payload = create_dependencies(
        db_session,
        prompt_variables=["question", "missing_context"],
    )

    run = EvaluationRunService(db_session).create_and_execute(payload)

    assert run.status == "completed"
    assert run.succeeded_cases == 0
    assert run.errored_cases == 2
    assert all(result.status == "error" for result in run.results)
    assert all(
        "Missing prompt variables" in (result.error_message or "")
        for result in run.results
    )


def test_service_rejects_unsupported_provider(db_session: Session) -> None:
    payload = create_dependencies(db_session, provider="ollama")

    with pytest.raises(EvaluationRunUnsupportedProviderError):
        EvaluationRunService(db_session).create_and_execute(payload)


def test_service_reports_missing_model(db_session: Session) -> None:
    payload = EvaluationRunCreate(
        registered_model_id=UUID("00000000-0000-0000-0000-000000000001"),
        prompt_version_id=UUID("00000000-0000-0000-0000-000000000002"),
        dataset_version_id=UUID("00000000-0000-0000-0000-000000000003"),
    )

    with pytest.raises(EvaluationRunNotFoundError):
        EvaluationRunService(db_session).create_and_execute(payload)
