import pytest
from pydantic import ValidationError

from app.schemas.evaluator import (
    EvaluationPolicy,
    ExactMatchEvaluator,
    JsonSchemaEvaluator,
    normalize_evaluation_policy,
)


def test_normalize_literal_text_as_exact_match() -> None:
    policy = normalize_evaluation_policy("Paris")

    assert policy is not None
    assert policy.mode == "all"
    assert policy.evaluators == [ExactMatchEvaluator(type="exact_match", value="Paris")]


def test_normalize_legacy_shorthand_as_composed_policy() -> None:
    policy = normalize_evaluation_policy(
        {
            "contains": "Paris",
            "forbidden_terms": ["London"],
        }
    )

    assert policy is not None
    assert [evaluator.type for evaluator in policy.evaluators] == [
        "contains",
        "forbidden_terms",
    ]


def test_canonical_policy_accepts_multiple_evaluators() -> None:
    policy = EvaluationPolicy.model_validate(
        {
            "mode": "any",
            "evaluators": [
                {"type": "contains", "value": "Paris"},
                {"type": "exact_match", "value": "PARIS", "case_sensitive": False},
            ],
        }
    )

    assert policy.mode == "any"
    assert len(policy.evaluators) == 2


def test_json_schema_evaluator_rejects_invalid_schema() -> None:
    with pytest.raises(ValidationError):
        JsonSchemaEvaluator(
            type="json_schema",
            schema={"type": "not-a-json-schema-type"},
        )


def test_shorthand_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="Unknown evaluator shorthand"):
        normalize_evaluation_policy(
            {
                "contains": "Paris",
                "unrecognized": True,
            }
        )
