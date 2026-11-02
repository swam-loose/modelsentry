from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.evaluation_run import EvaluationResult, EvaluationRun
from app.repositories.evaluation_run import EvaluationRunRepository
from app.schemas.run_comparison import (
    CaseComparisonRead,
    CaseOutcome,
    ComparisonOutcome,
    RunComparisonCreate,
    RunComparisonRead,
    RunMetricDelta,
    RunMetricSnapshot,
)


class RunComparisonNotFoundError(Exception):
    """Raised when either requested run does not exist."""


class RunComparisonConflictError(Exception):
    """Raised when two runs cannot be compared safely."""


class RunComparisonService:
    """Compare immutable run evidence without promoting either model automatically."""

    def __init__(self, session: Session) -> None:
        self.repository = EvaluationRunRepository(session)

    @staticmethod
    def _case_outcome(result: EvaluationResult) -> CaseOutcome:
        if result.status == "error":
            return "error"
        return result.evaluation_status

    @staticmethod
    def _quality_change(
        baseline: CaseOutcome,
        candidate: CaseOutcome,
    ) -> str:
        comparable_scores = {"failed": 0, "passed": 1}
        if baseline == candidate:
            return "unchanged"
        if baseline not in comparable_scores or candidate not in comparable_scores:
            return "inconclusive"
        if comparable_scores[candidate] > comparable_scores[baseline]:
            return "improved"
        return "regressed"

    @staticmethod
    def _quality_outcome(
        *,
        improved: int,
        regressed: int,
        inconclusive: int,
    ) -> ComparisonOutcome:
        if improved and regressed:
            return "mixed"
        if regressed:
            return "regressed"
        if improved:
            return "improved"
        if inconclusive:
            return "inconclusive"
        return "unchanged"

    @staticmethod
    def _performance_outcome(
        latency_delta: Decimal,
        cost_delta: Decimal,
    ) -> ComparisonOutcome:
        directions = {
            -1 if value < 0 else 1
            for value in (latency_delta, cost_delta)
            if value != 0
        }
        if not directions:
            return "unchanged"
        if directions == {-1}:
            return "improved"
        if directions == {1}:
            return "regressed"
        return "mixed"

    @staticmethod
    def _overall_outcome(
        quality: ComparisonOutcome,
        performance: ComparisonOutcome,
    ) -> ComparisonOutcome:
        if quality in {"mixed", "inconclusive"}:
            return quality
        if quality == "regressed":
            return "regressed"
        if quality == "improved":
            return "mixed" if performance == "regressed" else "improved"
        return performance

    @staticmethod
    def _snapshot(run: EvaluationRun) -> RunMetricSnapshot:
        return RunMetricSnapshot(
            run_id=run.id,
            model_identifier=run.model_identifier,
            passed_cases=run.passed_cases,
            failed_cases=run.failed_cases,
            errored_cases=run.errored_cases,
            pass_rate=run.pass_rate,
            average_latency_ms=run.average_latency_ms,
            p95_latency_ms=run.p95_latency_ms,
            total_latency_ms=run.total_latency_ms,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            total_tokens=run.total_tokens,
            estimated_cost_usd=run.estimated_cost_usd,
            token_usage_estimated=run.token_usage_estimated,
            approval_status=run.approval_status,
        )

    def _get_run(self, run_id: UUID) -> EvaluationRun:
        run = self.repository.get_by_id(run_id)
        if run is None:
            raise RunComparisonNotFoundError(
                f"Evaluation run '{run_id}' was not found."
            )
        return run

    def compare(self, payload: RunComparisonCreate) -> RunComparisonRead:
        baseline = self._get_run(payload.baseline_run_id)
        candidate = self._get_run(payload.candidate_run_id)
        if baseline.status != "completed" or candidate.status != "completed":
            raise RunComparisonConflictError(
                "Only completed evaluation runs can be compared."
            )
        if baseline.dataset_version_id != candidate.dataset_version_id:
            raise RunComparisonConflictError(
                "Runs must reference the same immutable dataset version."
            )

        baseline_results = {
            result.evaluation_case_id: result for result in baseline.results
        }
        candidate_results = {
            result.evaluation_case_id: result for result in candidate.results
        }
        if baseline_results.keys() != candidate_results.keys():
            raise RunComparisonConflictError(
                "Runs do not contain the same evaluation case identifiers."
            )

        cases: list[CaseComparisonRead] = []
        for baseline_result in baseline.results:
            candidate_result = candidate_results[baseline_result.evaluation_case_id]
            baseline_outcome = self._case_outcome(baseline_result)
            candidate_outcome = self._case_outcome(candidate_result)
            cases.append(
                CaseComparisonRead(
                    evaluation_case_id=baseline_result.evaluation_case_id,
                    position=baseline_result.position,
                    baseline_outcome=baseline_outcome,
                    candidate_outcome=candidate_outcome,
                    quality_change=self._quality_change(
                        baseline_outcome,
                        candidate_outcome,
                    ),
                    latency_delta_ms=(
                        candidate_result.latency_ms - baseline_result.latency_ms
                    ),
                    token_delta=(
                        candidate_result.total_tokens - baseline_result.total_tokens
                    ),
                    estimated_cost_delta_usd=(
                        candidate_result.estimated_cost_usd
                        - baseline_result.estimated_cost_usd
                    ),
                )
            )

        improved = sum(case.quality_change == "improved" for case in cases)
        regressed = sum(case.quality_change == "regressed" for case in cases)
        unchanged = sum(case.quality_change == "unchanged" for case in cases)
        inconclusive = sum(case.quality_change == "inconclusive" for case in cases)
        quality_outcome = self._quality_outcome(
            improved=improved,
            regressed=regressed,
            inconclusive=inconclusive,
        )
        average_latency_delta = (
            candidate.average_latency_ms - baseline.average_latency_ms
        )
        cost_delta = candidate.estimated_cost_usd - baseline.estimated_cost_usd
        performance_outcome = self._performance_outcome(
            average_latency_delta,
            cost_delta,
        )

        return RunComparisonRead(
            baseline=self._snapshot(baseline),
            candidate=self._snapshot(candidate),
            delta=RunMetricDelta(
                pass_rate=(
                    None
                    if baseline.pass_rate is None or candidate.pass_rate is None
                    else candidate.pass_rate - baseline.pass_rate
                ),
                average_latency_ms=average_latency_delta,
                p95_latency_ms=candidate.p95_latency_ms - baseline.p95_latency_ms,
                total_latency_ms=(
                    candidate.total_latency_ms - baseline.total_latency_ms
                ),
                total_tokens=candidate.total_tokens - baseline.total_tokens,
                estimated_cost_usd=cost_delta,
            ),
            quality_outcome=quality_outcome,
            performance_outcome=performance_outcome,
            overall_outcome=self._overall_outcome(
                quality_outcome,
                performance_outcome,
            ),
            improved_cases=improved,
            regressed_cases=regressed,
            unchanged_cases=unchanged,
            inconclusive_cases=inconclusive,
            cases=cases,
        )
