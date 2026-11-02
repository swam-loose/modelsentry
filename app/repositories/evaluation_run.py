from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.evaluation_dataset import EvaluationDatasetVersion
from app.models.evaluation_run import EvaluationResult, EvaluationRun
from app.models.prompt import PromptVersion
from app.models.registered_model import RegisteredModel
from app.schemas.evaluation_run import EvaluationRunCreate


class EvaluationRunRepository:
    """Persist run state transitions and ordered case-level results."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_registered_model(self, model_id: UUID) -> RegisteredModel | None:
        return self.session.get(RegisteredModel, model_id)

    def get_prompt_version(self, version_id: UUID) -> PromptVersion | None:
        return self.session.get(PromptVersion, version_id)

    def get_dataset_version(
        self,
        version_id: UUID,
    ) -> EvaluationDatasetVersion | None:
        statement = (
            select(EvaluationDatasetVersion)
            .where(EvaluationDatasetVersion.id == version_id)
            .options(selectinload(EvaluationDatasetVersion.cases))
        )
        return self.session.scalar(statement)

    def create_run(
        self,
        payload: EvaluationRunCreate,
        *,
        provider: str,
        model_identifier: str,
        total_cases: int,
    ) -> EvaluationRun:
        run = EvaluationRun(
            **payload.model_dump(),
            provider=provider,
            model_identifier=model_identifier,
            total_cases=total_cases,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def mark_running(self, run: EvaluationRun) -> EvaluationRun:
        run.status = "running"
        run.started_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(run)
        return run

    def complete_run(
        self,
        run: EvaluationRun,
        results: list[EvaluationResult],
    ) -> EvaluationRun:
        run.results.extend(results)
        run.succeeded_cases = sum(result.status == "succeeded" for result in results)
        run.errored_cases = sum(result.status == "error" for result in results)
        run.passed_cases = sum(
            result.evaluation_status == "passed" for result in results
        )
        run.failed_cases = sum(
            result.evaluation_status == "failed" for result in results
        )
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(run)
        return run

    def fail_run(self, run: EvaluationRun, error_message: str) -> EvaluationRun:
        run.status = "failed"
        run.error_message = error_message[:2000]
        run.completed_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_by_id(self, run_id: UUID) -> EvaluationRun | None:
        statement = (
            select(EvaluationRun)
            .where(EvaluationRun.id == run_id)
            .options(
                selectinload(EvaluationRun.results).selectinload(
                    EvaluationResult.checks
                )
            )
        )
        return self.session.scalar(statement)

    def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[EvaluationRun]:
        statement = (
            select(EvaluationRun)
            .order_by(EvaluationRun.created_at, EvaluationRun.id)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))
