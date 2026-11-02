from typing import Annotated, Literal

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
)

EvaluatorText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=20_000),
]
PolicyTerm = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


class ExactMatchEvaluator(BaseModel):
    """Compare provider output with one expected string."""

    type: Literal["exact_match"]
    value: EvaluatorText
    case_sensitive: bool = True
    strip: bool = True

    model_config = ConfigDict(extra="forbid")


class ContainsEvaluator(BaseModel):
    """Require one substring in provider output."""

    type: Literal["contains"]
    value: EvaluatorText
    case_sensitive: bool = True

    model_config = ConfigDict(extra="forbid")


class JsonEqualsEvaluator(BaseModel):
    """Compare parsed provider JSON with an expected JSON value."""

    type: Literal["json_equals"]
    expected: JsonValue

    model_config = ConfigDict(extra="forbid")


class JsonSchemaEvaluator(BaseModel):
    """Validate parsed provider JSON against a Draft 2020-12 schema."""

    type: Literal["json_schema"]
    schema_definition: dict[str, JsonValue] = Field(
        validation_alias="schema",
        serialization_alias="schema",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("schema_definition")
    @classmethod
    def schema_must_be_valid(
        cls,
        schema: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise ValueError("The supplied JSON Schema is invalid.") from error
        return schema


class RequiredTermsEvaluator(BaseModel):
    """Require all or any configured terms in provider output."""

    type: Literal["required_terms"]
    terms: list[PolicyTerm] = Field(min_length=1, max_length=100)
    match: Literal["all", "any"] = "all"
    case_sensitive: bool = False

    model_config = ConfigDict(extra="forbid")


class ForbiddenTermsEvaluator(BaseModel):
    """Reject provider output containing configured policy terms."""

    type: Literal["forbidden_terms"]
    terms: list[PolicyTerm] = Field(min_length=1, max_length=100)
    case_sensitive: bool = False

    model_config = ConfigDict(extra="forbid")


EvaluatorSpec = Annotated[
    ExactMatchEvaluator
    | ContainsEvaluator
    | JsonEqualsEvaluator
    | JsonSchemaEvaluator
    | RequiredTermsEvaluator
    | ForbiddenTermsEvaluator,
    Field(discriminator="type"),
]


class EvaluationPolicy(BaseModel):
    """Deterministic evaluator composition attached to one dataset case."""

    mode: Literal["all", "any"] = "all"
    evaluators: list[EvaluatorSpec] = Field(min_length=1, max_length=20)

    model_config = ConfigDict(extra="forbid")


def normalize_evaluation_policy(
    expected_output: JsonValue | None,
) -> EvaluationPolicy | None:
    """Normalize canonical policies, legacy shorthand, and literal expectations."""

    if expected_output is None:
        return None
    if isinstance(expected_output, str):
        return EvaluationPolicy(
            evaluators=[ExactMatchEvaluator(type="exact_match", value=expected_output)]
        )
    if not isinstance(expected_output, dict):
        return EvaluationPolicy(
            evaluators=[
                JsonEqualsEvaluator(type="json_equals", expected=expected_output)
            ]
        )
    if "evaluators" in expected_output:
        return EvaluationPolicy.model_validate(expected_output)

    shorthand_keys = {
        "contains",
        "exact_match",
        "forbidden_terms",
        "json_schema",
        "required_terms",
    }
    present_keys = shorthand_keys.intersection(expected_output)
    if not present_keys:
        return EvaluationPolicy(
            evaluators=[
                JsonEqualsEvaluator(type="json_equals", expected=expected_output)
            ]
        )

    unknown_keys = set(expected_output).difference(shorthand_keys | {"mode"})
    if unknown_keys:
        names = ", ".join(sorted(unknown_keys))
        raise ValueError(f"Unknown evaluator shorthand fields: {names}.")

    evaluators: list[EvaluatorSpec] = []
    if "exact_match" in expected_output:
        evaluators.append(
            ExactMatchEvaluator(
                type="exact_match",
                value=expected_output["exact_match"],
            )
        )
    if "contains" in expected_output:
        evaluators.append(
            ContainsEvaluator(
                type="contains",
                value=expected_output["contains"],
            )
        )
    if "json_schema" in expected_output:
        evaluators.append(
            JsonSchemaEvaluator(
                type="json_schema",
                schema=expected_output["json_schema"],
            )
        )
    if "required_terms" in expected_output:
        evaluators.append(
            RequiredTermsEvaluator(
                type="required_terms",
                terms=expected_output["required_terms"],
            )
        )
    if "forbidden_terms" in expected_output:
        evaluators.append(
            ForbiddenTermsEvaluator(
                type="forbidden_terms",
                terms=expected_output["forbidden_terms"],
            )
        )
    return EvaluationPolicy(
        mode=expected_output.get("mode", "all"),
        evaluators=evaluators,
    )
