from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.release_gate import ReleaseGateCreate, ReleaseGateVersionCreate


def test_release_gate_schema_defaults_are_conservative() -> None:
    payload = ReleaseGateCreate(name="Production Gate", slug="production-gate")
    version = payload.initial_version

    assert version.min_pass_rate == Decimal("1")
    assert version.max_errored_cases == 0
    assert version.require_human_approval is True
    assert version.require_no_quality_regressions is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_pass_rate", "1.01"),
        ("max_errored_cases", -1),
        ("max_average_latency_ms", "-0.001"),
        ("max_p95_latency_ms", -1),
        ("max_estimated_cost_usd", "-0.00000001"),
    ],
)
def test_release_gate_version_rejects_invalid_thresholds(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        ReleaseGateVersionCreate.model_validate({field: value})


def test_release_gate_rejects_invalid_slug() -> None:
    with pytest.raises(ValidationError):
        ReleaseGateCreate(name="Production Gate", slug="Invalid Gate")
