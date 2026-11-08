from app.models.prompt import Prompt, PromptVersion


def test_prompt_model_metadata() -> None:
    assert Prompt.__tablename__ == "prompts"
    assert set(Prompt.__table__.columns.keys()) == {
        "id",
        "name",
        "slug",
        "description",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert Prompt.__table__.columns["slug"].unique is True


def test_prompt_version_model_metadata() -> None:
    assert PromptVersion.__tablename__ == "prompt_versions"
    assert set(PromptVersion.__table__.columns.keys()) == {
        "id",
        "prompt_id",
        "version",
        "system_prompt",
        "user_prompt_template",
        "variables",
        "change_note",
        "created_at",
    }
