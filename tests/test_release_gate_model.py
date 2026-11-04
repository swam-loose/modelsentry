from app.models.release_gate import (
    ReleaseGate,
    ReleaseGateCheck,
    ReleaseGateEvaluation,
    ReleaseGateVersion,
)


def test_release_gate_model_metadata() -> None:
    assert ReleaseGate.__tablename__ == "release_gates"
    assert set(ReleaseGate.__table__.columns.keys()) == {
        "id",
        "name",
        "slug",
        "description",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert ReleaseGate.__table__.columns["slug"].unique is True


def test_release_gate_version_model_metadata() -> None:
    assert ReleaseGateVersion.__tablename__ == "release_gate_versions"
    assert set(ReleaseGateVersion.__table__.columns.keys()) == {
        "id",
        "release_gate_id",
        "version",
        "min_pass_rate",
        "max_errored_cases",
        "max_average_latency_ms",
        "max_p95_latency_ms",
        "max_estimated_cost_usd",
        "require_human_approval",
        "require_no_quality_regressions",
        "change_note",
        "created_at",
    }


def test_release_gate_evidence_model_metadata() -> None:
    assert ReleaseGateEvaluation.__tablename__ == "release_gate_evaluations"
    assert set(ReleaseGateEvaluation.__table__.columns.keys()) == {
        "id",
        "release_gate_version_id",
        "candidate_run_id",
        "baseline_run_id",
        "status",
        "created_at",
    }
    assert ReleaseGateCheck.__tablename__ == "release_gate_checks"
    assert set(ReleaseGateCheck.__table__.columns.keys()) == {
        "id",
        "evaluation_id",
        "position",
        "check_type",
        "passed",
        "expected_value",
        "actual_value",
        "message",
        "created_at",
    }
