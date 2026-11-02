from sqlalchemy.orm import Session

from app.models.evaluation_run import EvaluationCheck, EvaluationResult
from app.repositories.evaluation_dataset import EvaluationDatasetRepository
from app.repositories.evaluation_run import EvaluationRunRepository
from app.repositories.model_registry import ModelRegistryRepository
from app.repositories.prompt_registry import PromptRegistryRepository
from app.schemas.evaluation_dataset import (
    EvaluationCaseCreate,
    EvaluationDatasetCreate,
    EvaluationDatasetVersionCreate,
)
from app.schemas.evaluation_run import EvaluationRunCreate
from app.schemas.model import RegisteredModelCreate
from app.schemas.prompt import PromptCreate, PromptVersionCreate


def test_repository_persists_run_transitions_and_results(
    db_session: Session,
) -> None:
    model = ModelRegistryRepository(db_session).create(
        RegisteredModelCreate(
            name="Mock Evaluator",
            slug="mock-evaluator",
            provider="mock",
            model_identifier="deterministic-v1",
        )
    )
    prompt = PromptRegistryRepository(db_session).create(
        PromptCreate(
            name="Geography Answer",
            slug="geography-answer",
            initial_version=PromptVersionCreate(
                user_prompt_template="Question: {{question}}",
                variables=["question"],
            ),
        )
    )
    dataset_repository = EvaluationDatasetRepository(db_session)
    dataset = dataset_repository.create_dataset(
        EvaluationDatasetCreate(name="Geography QA", slug="geography-qa")
    )
    dataset_version = dataset_repository.create_version(
        dataset.id,
        EvaluationDatasetVersionCreate(
            cases=[
                EvaluationCaseCreate(
                    case_key="capital-france",
                    input={"question": "What is the capital of France?"},
                )
            ]
        ),
        "a" * 64,
    )
    repository = EvaluationRunRepository(db_session)
    payload = EvaluationRunCreate(
        registered_model_id=model.id,
        prompt_version_id=prompt.versions[0].id,
        dataset_version_id=dataset_version.id,
    )

    run = repository.create_run(
        payload,
        provider="mock",
        model_identifier="deterministic-v1",
        total_cases=1,
    )
    repository.mark_running(run)
    repository.complete_run(
        run,
        [
            EvaluationResult(
                evaluation_case_id=dataset_version.cases[0].id,
                position=0,
                status="succeeded",
                evaluation_status="passed",
                rendered_user_prompt="Question: What is the capital of France?",
                output_text="Paris",
                latency_ms=10,
                checks=[
                    EvaluationCheck(
                        position=0,
                        evaluator_type="contains",
                        passed=True,
                        expected_value="Paris",
                        actual_value="Paris",
                        message="Output contained the required text.",
                    )
                ],
            )
        ],
    )

    assert run.status == "completed"
    assert run.started_at is not None
    assert run.completed_at is not None
    assert run.succeeded_cases == 1
    assert run.passed_cases == 1
    assert run.failed_cases == 0
    assert run.pass_rate == 1.0
    assert run.results[0].checks[0].evaluator_type == "contains"
    assert repository.get_by_id(run.id) is run
    assert repository.list_all() == [run]
