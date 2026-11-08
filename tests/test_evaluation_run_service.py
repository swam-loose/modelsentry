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
    assert run.passed_cases == 2
    assert run.failed_cases == 0
    assert run.pass_rate == 1.0
    assert [result.output_text for result in run.results] == [
        "Paris is the capital of France.",
        "Brasilia is the capital of Brazil.",
    ]
    assert all(5 <= result.latency_ms <= 50 for result in run.results)
    assert all(result.evaluation_status == "passed" for result in run.results)
    assert all(result.checks[0].evaluator_type == "contains" for result in run.results)
    assert run.input_tokens > 0
    assert run.output_tokens > 0
    assert run.total_tokens == run.input_tokens + run.output_tokens
    assert run.total_latency_ms == sum(result.latency_ms for result in run.results)
    assert run.average_latency_ms > 0
    assert run.p95_latency_ms > 0


def test_service_records_case_level_rendering_errors(db_session: Session) -> None:
    payload = create_dependencies(
        db_session,
        prompt_variables=["question", "missing_context"],
    )

    run = EvaluationRunService(db_session).create_and_execute(payload)

    assert run.status == "completed"
    assert run.succeeded_cases == 0
    assert run.errored_cases == 2
    assert run.passed_cases == 0
    assert run.failed_cases == 0
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


def test_service_persists_failed_policy_evidence(db_session: Session) -> None:
    payload = create_dependencies(db_session)
    dataset_version = EvaluationRunService(db_session).repository.get_dataset_version(
        payload.dataset_version_id
    )
    assert dataset_version is not None
    dataset_version.cases[0].expected_output = {
        "required_terms": ["Paris", "France"],
        "forbidden_terms": ["capital"],
    }
    db_session.commit()

    run = EvaluationRunService(db_session).create_and_execute(payload)

    assert run.status == "completed"
    assert run.passed_cases == 1
    assert run.failed_cases == 1
    assert run.pass_rate == 0.5
    first_result = run.results[0]
    assert first_result.evaluation_status == "failed"
    assert [check.passed for check in first_result.checks] == [True, False]
    assert "capital" in first_result.checks[1].message
