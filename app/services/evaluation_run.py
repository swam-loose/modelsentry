from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.evaluation.evaluators import DeterministicEvaluatorEngine
from app.evaluation.renderer import PromptRenderer, PromptRenderingError
from app.models.evaluation_run import EvaluationCheck, EvaluationResult, EvaluationRun
from app.providers.mock import MockModelProvider
from app.repositories.evaluation_run import EvaluationRunRepository
from app.schemas.evaluation_run import EvaluationRunCreate


class EvaluationRunNotFoundError(Exception):
    """Raised when a run or one of its immutable inputs does not exist."""


class EvaluationRunUnsupportedProviderError(Exception):
    """Raised when synchronous execution cannot use the selected provider."""


class EvaluationRunService:
    """Execute deterministic local model evaluations and persist evidence."""

    def __init__(self, session: Session) -> None:
        self.repository = EvaluationRunRepository(session)

    @staticmethod
    def estimate_cost(
        *,
        input_tokens: int,
        output_tokens: int,
        input_cost_per_million: Decimal,
        output_cost_per_million: Decimal,
    ) -> Decimal:
        """Calculate an auditable cost estimate from snapshotted rates."""

        cost = (
            Decimal(input_tokens) * input_cost_per_million
            + Decimal(output_tokens) * output_cost_per_million
        ) / Decimal(1_000_000)
        return cost.quantize(Decimal("0.00000001"))

    def create_and_execute(self, payload: EvaluationRunCreate) -> EvaluationRun:
        model = self.repository.get_registered_model(payload.registered_model_id)
        if model is None:
            raise EvaluationRunNotFoundError(
                f"Registered model '{payload.registered_model_id}' was not found."
            )
        if not model.is_active:
            raise EvaluationRunUnsupportedProviderError(
                "The selected registered model is inactive."
            )
        if model.provider != "mock":
            raise EvaluationRunUnsupportedProviderError(
                f"Provider '{model.provider}' is not executable in local version 0.1."
            )

        prompt_version = self.repository.get_prompt_version(payload.prompt_version_id)
        if prompt_version is None:
            raise EvaluationRunNotFoundError(
                f"Prompt version '{payload.prompt_version_id}' was not found."
            )

        dataset_version = self.repository.get_dataset_version(
            payload.dataset_version_id
        )
        if dataset_version is None:
            raise EvaluationRunNotFoundError(
                f"Dataset version '{payload.dataset_version_id}' was not found."
            )

        run = self.repository.create_run(
            payload,
            provider=model.provider,
            model_identifier=model.model_identifier,
            total_cases=len(dataset_version.cases),
            input_cost_per_million=model.input_cost_per_million,
            output_cost_per_million=model.output_cost_per_million,
            token_usage_estimated=True,
        )
        self.repository.mark_running(run)
        provider = MockModelProvider(model.model_identifier)
        results: list[EvaluationResult] = []

        try:
            for case in dataset_version.cases:
                rendered_system_prompt = prompt_version.system_prompt
                rendered_user_prompt = prompt_version.user_prompt_template
                try:
                    if prompt_version.system_prompt is not None:
                        rendered_system_prompt = PromptRenderer.render(
                            prompt_version.system_prompt,
                            variables=prompt_version.variables,
                            values=case.input_data,
                        )
                    rendered_user_prompt = PromptRenderer.render(
                        prompt_version.user_prompt_template,
                        variables=prompt_version.variables,
                        values=case.input_data,
                    )
                    response = provider.generate(
                        rendered_system_prompt=rendered_system_prompt,
                        rendered_user_prompt=rendered_user_prompt,
                        case_input=case.input_data,
                    )
                    report = DeterministicEvaluatorEngine.evaluate(
                        response.output_text,
                        case.expected_output,
                    )
                    result = EvaluationResult(
                        evaluation_case_id=case.id,
                        position=case.position,
                        status="succeeded",
                        evaluation_status=report.status,
                        rendered_system_prompt=rendered_system_prompt,
                        rendered_user_prompt=rendered_user_prompt,
                        output_text=response.output_text,
                        latency_ms=response.latency_ms,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        estimated_cost_usd=self.estimate_cost(
                            input_tokens=response.input_tokens,
                            output_tokens=response.output_tokens,
                            input_cost_per_million=run.input_cost_per_million,
                            output_cost_per_million=run.output_cost_per_million,
                        ),
                        token_usage_estimated=True,
                    )
                    result.checks.extend(
                        EvaluationCheck(
                            position=position,
                            evaluator_type=outcome.evaluator_type,
                            passed=outcome.passed,
                            expected_value=outcome.expected_value,
                            actual_value=outcome.actual_value,
                            message=outcome.message,
                        )
                        for position, outcome in enumerate(report.outcomes)
                    )
                    results.append(result)
                except PromptRenderingError as error:
                    results.append(
                        EvaluationResult(
                            evaluation_case_id=case.id,
                            position=case.position,
                            status="error",
                            rendered_system_prompt=rendered_system_prompt,
                            rendered_user_prompt=rendered_user_prompt,
                            error_message=str(error),
                            latency_ms=0,
                        )
                    )
            self.repository.complete_run(run, results)
        except Exception as error:
            self.repository.fail_run(run, f"Evaluation execution failed: {error}")

        return self.get_run(run.id)

    def get_run(self, run_id: UUID) -> EvaluationRun:
        run = self.repository.get_by_id(run_id)
        if run is None:
            raise EvaluationRunNotFoundError(
                f"Evaluation run '{run_id}' was not found."
            )
        return run

    def list_runs(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[EvaluationRun]:
        return self.repository.list_all(offset=offset, limit=limit)
