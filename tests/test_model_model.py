from app.models.registered_model import RegisteredModel


def test_registered_model_metadata() -> None:
    assert RegisteredModel.__tablename__ == "registered_models"
    assert set(RegisteredModel.__table__.columns.keys()) == {
        "id",
        "name",
        "slug",
        "provider",
        "model_identifier",
        "description",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert RegisteredModel.__table__.columns["slug"].unique is True
