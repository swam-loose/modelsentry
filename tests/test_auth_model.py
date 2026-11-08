from app.models.auth import ApiKey, UserAccount


def test_user_account_model_metadata() -> None:
    assert UserAccount.__tablename__ == "user_accounts"
    assert set(UserAccount.__table__.columns.keys()) == {
        "id",
        "email",
        "display_name",
        "role",
        "bootstrap_slot",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert UserAccount.__table__.columns["email"].unique is True


def test_api_key_model_excludes_raw_secret_storage() -> None:
    assert ApiKey.__tablename__ == "api_keys"
    assert set(ApiKey.__table__.columns.keys()) == {
        "id",
        "user_id",
        "label",
        "key_prefix",
        "key_hash",
        "expires_at",
        "last_used_at",
        "revoked_at",
        "created_at",
    }
    assert "api_key" not in ApiKey.__table__.columns
    assert ApiKey.__table__.columns["key_hash"].unique is True
