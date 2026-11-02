import pytest

from app.evaluation.evaluators import DeterministicEvaluatorEngine


@pytest.mark.parametrize(
    ("output", "expectation", "expected_status"),
    [
        (" Paris ", "Paris", "passed"),
        ("Paris is in France.", {"contains": "Paris"}, "passed"),
        ("London", {"contains": "Paris"}, "failed"),
        ('{"answer":"Paris"}', {"answer": "Paris"}, "passed"),
        ('{"answer":"London"}', {"answer": "Paris"}, "failed"),
    ],
)
def test_evaluate_literal_and_legacy_expectations(
    output: str,
    expectation: object,
    expected_status: str,
) -> None:
    report = DeterministicEvaluatorEngine.evaluate(output, expectation)

    assert report.status == expected_status
    assert len(report.outcomes) == 1


def test_evaluate_json_schema_with_evidence() -> None:
    schema = {
        "type": "object",
        "required": ["answer", "confidence"],
        "properties": {
            "answer": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "additionalProperties": False,
    }

    passing = DeterministicEvaluatorEngine.evaluate(
        '{"answer":"Paris","confidence":0.98}',
        {"json_schema": schema},
    )
    failing = DeterministicEvaluatorEngine.evaluate(
        '{"answer":"Paris","confidence":2}',
        {"json_schema": schema},
    )

    assert passing.status == "passed"
    assert passing.outcomes[0].passed is True
    assert failing.status == "failed"
    assert "JSON Schema violation" in failing.outcomes[0].message


def test_evaluate_required_and_forbidden_terms() -> None:
    report = DeterministicEvaluatorEngine.evaluate(
        "Paris is the capital of France.",
        {
            "required_terms": ["paris", "france"],
            "forbidden_terms": ["uncertain", "london"],
        },
    )

    assert report.status == "passed"
    assert [outcome.passed for outcome in report.outcomes] == [True, True]


def test_any_mode_passes_when_one_evaluator_passes() -> None:
    report = DeterministicEvaluatorEngine.evaluate(
        "Paris",
        {
            "mode": "any",
            "evaluators": [
                {"type": "exact_match", "value": "London"},
                {"type": "contains", "value": "Paris"},
            ],
        },
    )

    assert report.status == "passed"
    assert [outcome.passed for outcome in report.outcomes] == [False, True]


def test_missing_expectation_is_not_evaluated() -> None:
    report = DeterministicEvaluatorEngine.evaluate("Any output", None)

    assert report.status == "not_evaluated"
    assert report.outcomes == ()
