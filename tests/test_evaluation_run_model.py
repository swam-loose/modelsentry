from app.models.evaluation_run import EvaluationResult, EvaluationRun


def test_evaluation_run_model_metadata() -> None:
    assert EvaluationRun.__tablename__ == "evaluation_runs"
    assert set(EvaluationRun.__table__.columns.keys()) == {
        "id",
        "registered_model_id",
        "prompt_version_id",
        "dataset_version_id",
        "provider",
        "model_identifier",
        "status",
        "total_cases",
        "succeeded_cases",
        "errored_cases",
        "error_message",
        "created_at",
        "started_at",
        "completed_at",
    }


def test_evaluation_result_model_metadata() -> None:
    assert EvaluationResult.__tablename__ == "evaluation_results"
    assert set(EvaluationResult.__table__.columns.keys()) == {
        "id",
        "run_id",
        "evaluation_case_id",
        "position",
        "status",
        "rendered_system_prompt",
        "rendered_user_prompt",
        "output_text",
        "error_message",
        "latency_ms",
        "created_at",
    }
