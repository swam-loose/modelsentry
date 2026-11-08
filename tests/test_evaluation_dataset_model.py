from app.models.evaluation_dataset import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationDatasetVersion,
)


def test_evaluation_dataset_model_metadata() -> None:
    assert EvaluationDataset.__tablename__ == "evaluation_datasets"
    assert set(EvaluationDataset.__table__.columns.keys()) == {
        "id",
        "name",
        "slug",
        "description",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert EvaluationDataset.__table__.columns["slug"].unique is True


def test_evaluation_dataset_version_model_metadata() -> None:
    assert EvaluationDatasetVersion.__tablename__ == "evaluation_dataset_versions"
    assert set(EvaluationDatasetVersion.__table__.columns.keys()) == {
        "id",
        "dataset_id",
        "version",
        "content_sha256",
        "case_count",
        "change_note",
        "created_at",
    }


def test_evaluation_case_model_metadata() -> None:
    assert EvaluationCase.__tablename__ == "evaluation_cases"
    assert set(EvaluationCase.__table__.columns.keys()) == {
        "id",
        "dataset_version_id",
        "position",
        "case_key",
        "input_data",
        "expected_output",
        "metadata",
        "created_at",
    }
