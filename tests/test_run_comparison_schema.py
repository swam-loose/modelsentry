from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.run_comparison import RunComparisonCreate


def test_comparison_schema_accepts_distinct_runs() -> None:
    payload = RunComparisonCreate(
        baseline_run_id=uuid4(),
        candidate_run_id=uuid4(),
    )

    assert payload.baseline_run_id != payload.candidate_run_id


def test_comparison_schema_rejects_same_run() -> None:
    run_id = uuid4()

    with pytest.raises(ValidationError, match="must be different"):
        RunComparisonCreate(
            baseline_run_id=run_id,
            candidate_run_id=run_id,
        )
