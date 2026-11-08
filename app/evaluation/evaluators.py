import json
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Literal

from jsonschema import Draft202012Validator
from pydantic import JsonValue

from app.schemas.evaluator import (
    ContainsEvaluator,
    EvaluationPolicy,
    ExactMatchEvaluator,
    ForbiddenTermsEvaluator,
    JsonEqualsEvaluator,
    JsonSchemaEvaluator,
    RequiredTermsEvaluator,
    normalize_evaluation_policy,
)

EvaluationStatus = Literal["not_evaluated", "passed", "failed"]


@dataclass(frozen=True, slots=True)
class EvaluatorOutcome:
    """One deterministic check and the evidence supporting its conclusion."""

    evaluator_type: str
    passed: bool
    expected_value: JsonValue
    actual_value: JsonValue
    message: str


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Combined deterministic result for one model response."""

    status: EvaluationStatus
    outcomes: tuple[EvaluatorOutcome, ...]


class DeterministicEvaluatorEngine:
    """Evaluate model output without network calls or probabilistic judges."""

    @classmethod
    def evaluate(
        cls,
        output_text: str,
        expected_output: JsonValue | None,
    ) -> EvaluationReport:
        policy = normalize_evaluation_policy(expected_output)
        if policy is None:
            return EvaluationReport(status="not_evaluated", outcomes=())

        outcomes = tuple(
            cls._evaluate_spec(output_text, evaluator)
            for evaluator in policy.evaluators
        )
        passed = cls._combine(policy, outcomes)
        return EvaluationReport(
            status="passed" if passed else "failed",
            outcomes=outcomes,
        )

    @staticmethod
    def _combine(
        policy: EvaluationPolicy,
        outcomes: tuple[EvaluatorOutcome, ...],
    ) -> bool:
        checks = [outcome.passed for outcome in outcomes]
        return all(checks) if policy.mode == "all" else any(checks)

    @classmethod
    def _evaluate_spec(
        cls,
        output_text: str,
        evaluator: object,
    ) -> EvaluatorOutcome:
        if isinstance(evaluator, ExactMatchEvaluator):
            actual = output_text.strip() if evaluator.strip else output_text
            expected = evaluator.value.strip() if evaluator.strip else evaluator.value
            passed = cls._compare_text(
                actual,
                expected,
                case_sensitive=evaluator.case_sensitive,
            )
            return EvaluatorOutcome(
                evaluator_type=evaluator.type,
                passed=passed,
                expected_value=evaluator.value,
                actual_value=output_text,
                message="Output exactly matched the expected text."
                if passed
                else "Output did not exactly match the expected text.",
            )

        if isinstance(evaluator, ContainsEvaluator):
            actual = cls._normalize_case(
                output_text,
                case_sensitive=evaluator.case_sensitive,
            )
            expected = cls._normalize_case(
                evaluator.value,
                case_sensitive=evaluator.case_sensitive,
            )
            passed = expected in actual
            return EvaluatorOutcome(
                evaluator_type=evaluator.type,
                passed=passed,
                expected_value=evaluator.value,
                actual_value=output_text,
                message="Output contained the required text."
                if passed
                else "Output did not contain the required text.",
            )

        if isinstance(evaluator, JsonEqualsEvaluator):
            actual_json, parse_error = cls._parse_json(output_text)
            passed = parse_error is None and actual_json == evaluator.expected
            return EvaluatorOutcome(
                evaluator_type=evaluator.type,
                passed=passed,
                expected_value=evaluator.expected,
                actual_value=actual_json if parse_error is None else output_text,
                message=(
                    "Parsed JSON exactly matched the expected value."
                    if passed
                    else parse_error or "Parsed JSON did not match the expected value."
                ),
            )

        if isinstance(evaluator, JsonSchemaEvaluator):
            return cls._evaluate_json_schema(output_text, evaluator)

        if isinstance(evaluator, RequiredTermsEvaluator):
            normalized_output = cls._normalize_case(
                output_text,
                case_sensitive=evaluator.case_sensitive,
            )
            normalized_terms = [
                cls._normalize_case(term, case_sensitive=evaluator.case_sensitive)
                for term in evaluator.terms
            ]
            matches = [term in normalized_output for term in normalized_terms]
            passed = all(matches) if evaluator.match == "all" else any(matches)
            missing_terms = [
                term
                for term, matched in zip(evaluator.terms, matches, strict=True)
                if not matched
            ]
            return EvaluatorOutcome(
                evaluator_type=evaluator.type,
                passed=passed,
                expected_value=evaluator.terms,
                actual_value=output_text,
                message="Output satisfied the required-terms policy."
                if passed
                else f"Missing required terms: {', '.join(missing_terms)}.",
            )

        if isinstance(evaluator, ForbiddenTermsEvaluator):
            normalized_output = cls._normalize_case(
                output_text,
                case_sensitive=evaluator.case_sensitive,
            )
            found_terms = [
                term
                for term in evaluator.terms
                if cls._normalize_case(
                    term,
                    case_sensitive=evaluator.case_sensitive,
                )
                in normalized_output
            ]
            passed = not found_terms
            return EvaluatorOutcome(
                evaluator_type=evaluator.type,
                passed=passed,
                expected_value=evaluator.terms,
                actual_value=output_text,
                message="Output contained no forbidden terms."
                if passed
                else f"Found forbidden terms: {', '.join(found_terms)}.",
            )

        raise TypeError(f"Unsupported evaluator type: {type(evaluator).__name__}.")

    @classmethod
    def _evaluate_json_schema(
        cls,
        output_text: str,
        evaluator: JsonSchemaEvaluator,
    ) -> EvaluatorOutcome:
        actual_json, parse_error = cls._parse_json(output_text)
        if parse_error is not None:
            return EvaluatorOutcome(
                evaluator_type=evaluator.type,
                passed=False,
                expected_value=evaluator.schema_definition,
                actual_value=output_text,
                message=parse_error,
            )

        validator = Draft202012Validator(evaluator.schema_definition)
        errors = sorted(
            validator.iter_errors(actual_json),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
        if not errors:
            return EvaluatorOutcome(
                evaluator_type=evaluator.type,
                passed=True,
                expected_value=evaluator.schema_definition,
                actual_value=actual_json,
                message="Parsed JSON satisfied the configured schema.",
            )

        first_error = errors[0]
        path = ".".join(str(part) for part in first_error.absolute_path) or "$"
        return EvaluatorOutcome(
            evaluator_type=evaluator.type,
            passed=False,
            expected_value=evaluator.schema_definition,
            actual_value=actual_json,
            message=f"JSON Schema violation at {path}: {first_error.message}",
        )

    @staticmethod
    def _parse_json(output_text: str) -> tuple[JsonValue, str | None]:
        try:
            return json.loads(output_text), None
        except JSONDecodeError:
            return None, "Output was not valid JSON."

    @staticmethod
    def _normalize_case(value: str, *, case_sensitive: bool) -> str:
        return value if case_sensitive else value.casefold()

    @classmethod
    def _compare_text(
        cls,
        actual: str,
        expected: str,
        *,
        case_sensitive: bool,
    ) -> bool:
        return cls._normalize_case(
            actual,
            case_sensitive=case_sensitive,
        ) == cls._normalize_case(
            expected,
            case_sensitive=case_sensitive,
        )
