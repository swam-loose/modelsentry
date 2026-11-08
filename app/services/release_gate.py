from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.evaluation_run import EvaluationRun
from app.models.release_gate import (
    ReleaseGate,
    ReleaseGateCheck,
    ReleaseGateEvaluation,
    ReleaseGateVersion,
)
from app.repositories.evaluation_run import EvaluationRunRepository
from app.repositories.release_gate import ReleaseGateRepository
from app.schemas.release_gate import (
    ReleaseGateCreate,
    ReleaseGateEvaluationCreate,
    ReleaseGateVersionCreate,
)
from app.schemas.run_comparison import RunComparisonCreate
from app.services.run_comparison import (
    RunComparisonConflictError,
    RunComparisonService,
)


class ReleaseGateConflictError(Exception):
    """Raised for duplicate gates or evidence that cannot be evaluated safely."""


class ReleaseGateNotFoundError(Exception):
    """Raised when a gate, version, evaluation, or run does not exist."""


class ReleaseGateService:
    """Evaluate reproducible release criteria and persist every decision."""

    def __init__(self, session: Session) -> None:
        self.repository = ReleaseGateRepository(session)
        self.run_repository = EvaluationRunRepository(session)
        self.comparison_service = RunComparisonService(session)

    def create_gate(self, payload: ReleaseGateCreate) -> ReleaseGate:
        if self.repository.get_by_slug(payload.slug) is not None:
            raise ReleaseGateConflictError(
                f"A release gate with slug '{payload.slug}' already exists."
            )
        try:
            return self.repository.create(payload)
        except IntegrityError as error:
            raise ReleaseGateConflictError(
                "The release gate conflicts with an existing policy."
            ) from error

    def get_gate(self, gate_id: UUID) -> ReleaseGate:
        gate = self.repository.get_by_id(gate_id)
        if gate is None:
            raise ReleaseGateNotFoundError(f"Release gate '{gate_id}' was not found.")
        return gate

    def list_gates(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ReleaseGate]:
        return self.repository.list_all(offset=offset, limit=limit)

    def create_version(
        self,
        gate_id: UUID,
        payload: ReleaseGateVersionCreate,
    ) -> ReleaseGateVersion:
        self.get_gate(gate_id)
        try:
            return self.repository.create_version(gate_id, payload)
        except IntegrityError as error:
            raise ReleaseGateConflictError(
                "The release-gate version conflicts with an existing version."
            ) from error

    def get_evaluation(self, evaluation_id: UUID) -> ReleaseGateEvaluation:
        evaluation = self.repository.get_evaluation(evaluation_id)
        if evaluation is None:
            raise ReleaseGateNotFoundError(
                f"Release-gate evaluation '{evaluation_id}' was not found."
            )
        return evaluation

    def list_evaluations(
        self,
        gate_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ReleaseGateEvaluation]:
        self.get_gate(gate_id)
        return self.repository.list_evaluations(
            gate_id,
            offset=offset,
            limit=limit,
        )

    def _get_completed_run(self, run_id: UUID) -> EvaluationRun:
        run = self.run_repository.get_by_id(run_id)
        if run is None:
            raise ReleaseGateNotFoundError(f"Evaluation run '{run_id}' was not found.")
        if run.status != "completed":
            raise ReleaseGateConflictError(
                "Only completed evaluation runs can be evaluated by a release gate."
            )
        return run

    @staticmethod
    def _check(
        checks: list[ReleaseGateCheck],
        *,
        check_type: str,
        passed: bool,
        expected_value: object,
        actual_value: object,
        message: str,
    ) -> None:
        checks.append(
            ReleaseGateCheck(
                position=len(checks),
                check_type=check_type,
                passed=passed,
                expected_value=expected_value,
                actual_value=actual_value,
                message=message,
            )
        )

    def evaluate(
        self,
        gate_id: UUID,
        payload: ReleaseGateEvaluationCreate,
    ) -> ReleaseGateEvaluation:
        self.get_gate(gate_id)
        version = self.repository.get_latest_version(gate_id)
        if version is None:
            raise ReleaseGateNotFoundError(
                f"Release gate '{gate_id}' has no policy version."
            )
        candidate = self._get_completed_run(payload.candidate_run_id)
        baseline = None
        if payload.baseline_run_id is not None:
            if payload.baseline_run_id == payload.candidate_run_id:
                raise ReleaseGateConflictError(
                    "Baseline and candidate runs must be different."
                )
            baseline = self._get_completed_run(payload.baseline_run_id)
        if version.require_no_quality_regressions and baseline is None:
            raise ReleaseGateConflictError(
                "This gate requires a baseline run for regression evidence."
            )

        checks: list[ReleaseGateCheck] = []
        pass_rate = (
            None if candidate.pass_rate is None else Decimal(str(candidate.pass_rate))
        )
        pass_rate_passed = pass_rate is not None and pass_rate >= version.min_pass_rate
        self._check(
            checks,
            check_type="minimum_pass_rate",
            passed=pass_rate_passed,
            expected_value=str(version.min_pass_rate),
            actual_value=None if pass_rate is None else str(pass_rate),
            message="Candidate pass rate met the configured minimum."
            if pass_rate_passed
            else "Candidate pass rate did not meet the configured minimum.",
        )
        error_count_passed = candidate.errored_cases <= version.max_errored_cases
        self._check(
            checks,
            check_type="maximum_errored_cases",
            passed=error_count_passed,
            expected_value=version.max_errored_cases,
            actual_value=candidate.errored_cases,
            message="Candidate errored cases stayed within the configured maximum."
            if error_count_passed
            else "Candidate errored cases exceeded the configured maximum.",
        )

        if version.max_average_latency_ms is not None:
            passed = candidate.average_latency_ms <= version.max_average_latency_ms
            self._check(
                checks,
                check_type="maximum_average_latency_ms",
                passed=passed,
                expected_value=str(version.max_average_latency_ms),
                actual_value=str(candidate.average_latency_ms),
                message="Candidate average latency stayed within the maximum."
                if passed
                else "Candidate average latency exceeded the maximum.",
            )
        if version.max_p95_latency_ms is not None:
            passed = candidate.p95_latency_ms <= version.max_p95_latency_ms
            self._check(
                checks,
                check_type="maximum_p95_latency_ms",
                passed=passed,
                expected_value=version.max_p95_latency_ms,
                actual_value=candidate.p95_latency_ms,
                message="Candidate p95 latency stayed within the maximum."
                if passed
                else "Candidate p95 latency exceeded the maximum.",
            )
        if version.max_estimated_cost_usd is not None:
            passed = candidate.estimated_cost_usd <= version.max_estimated_cost_usd
            self._check(
                checks,
                check_type="maximum_estimated_cost_usd",
                passed=passed,
                expected_value=str(version.max_estimated_cost_usd),
                actual_value=str(candidate.estimated_cost_usd),
                message="Candidate estimated cost stayed within the maximum."
                if passed
                else "Candidate estimated cost exceeded the maximum.",
            )
        if version.require_human_approval:
            passed = candidate.approval_status == "approved"
            self._check(
                checks,
                check_type="human_approval",
                passed=passed,
                expected_value="approved",
                actual_value=candidate.approval_status,
                message="Candidate received all requested human approvals."
                if passed
                else "Candidate has not received all requested human approvals.",
            )
        if version.require_no_quality_regressions and baseline is not None:
            try:
                comparison = self.comparison_service.compare(
                    RunComparisonCreate(
                        baseline_run_id=baseline.id,
                        candidate_run_id=candidate.id,
                    )
                )
            except RunComparisonConflictError as error:
                raise ReleaseGateConflictError(str(error)) from error
            accepted_outcomes = {"improved", "unchanged"}
            passed = comparison.quality_outcome in accepted_outcomes
            self._check(
                checks,
                check_type="quality_regression",
                passed=passed,
                expected_value=sorted(accepted_outcomes),
                actual_value=comparison.quality_outcome,
                message="Candidate introduced no deterministic quality regression."
                if passed
                else "Candidate introduced or could not rule out quality regression.",
            )

        evaluation_status = (
            "passed" if all(check.passed for check in checks) else "failed"
        )
        return self.repository.create_evaluation(
            version.id,
            payload,
            evaluation_status=evaluation_status,
            checks=checks,
        )
