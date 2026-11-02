from decimal import Decimal

import pytest

from app.services.run_comparison import RunComparisonService


@pytest.mark.parametrize(
    ("baseline", "candidate", "expected"),
    [
        ("passed", "passed", "unchanged"),
        ("failed", "passed", "improved"),
        ("passed", "failed", "regressed"),
        ("error", "passed", "inconclusive"),
    ],
)
def test_case_quality_change(
    baseline: str,
    candidate: str,
    expected: str,
) -> None:
    assert RunComparisonService._quality_change(baseline, candidate) == expected


@pytest.mark.parametrize(
    ("improved", "regressed", "inconclusive", "expected"),
    [
        (1, 1, 0, "mixed"),
        (0, 1, 0, "regressed"),
        (1, 0, 0, "improved"),
        (0, 0, 1, "inconclusive"),
        (0, 0, 0, "unchanged"),
    ],
)
def test_quality_outcome_aggregation(
    improved: int,
    regressed: int,
    inconclusive: int,
    expected: str,
) -> None:
    assert (
        RunComparisonService._quality_outcome(
            improved=improved,
            regressed=regressed,
            inconclusive=inconclusive,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("latency", "cost", "expected"),
    [
        ("0", "0", "unchanged"),
        ("-1", "-0.01", "improved"),
        ("1", "0.01", "regressed"),
        ("-1", "0.01", "mixed"),
    ],
)
def test_performance_outcome(
    latency: str,
    cost: str,
    expected: str,
) -> None:
    assert (
        RunComparisonService._performance_outcome(
            Decimal(latency),
            Decimal(cost),
        )
        == expected
    )


@pytest.mark.parametrize(
    ("quality", "performance", "expected"),
    [
        ("mixed", "improved", "mixed"),
        ("inconclusive", "unchanged", "inconclusive"),
        ("regressed", "improved", "regressed"),
        ("improved", "regressed", "mixed"),
        ("improved", "unchanged", "improved"),
        ("unchanged", "improved", "improved"),
    ],
)
def test_overall_outcome(
    quality: str,
    performance: str,
    expected: str,
) -> None:
    assert RunComparisonService._overall_outcome(quality, performance) == expected
