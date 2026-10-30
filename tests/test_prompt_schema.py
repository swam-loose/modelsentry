import pytest
from pydantic import ValidationError

from app.schemas.prompt import PromptCreate, PromptVersionCreate


def test_prompt_create_accepts_and_normalizes_valid_data() -> None:
    payload = PromptCreate(
        name="  Support Answer  ",
        slug="support-answer",
        initial_version={
            "system_prompt": "  Answer only from supplied evidence.  ",
            "user_prompt_template": "  Answer {{question}}.  ",
            "variables": ["question"],
        },
    )

    assert payload.name == "Support Answer"
    assert payload.initial_version.system_prompt == (
        "Answer only from supplied evidence."
    )
    assert payload.initial_version.user_prompt_template == "Answer {{question}}."


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("slug", "Invalid Slug"),
        ("name", ""),
    ],
)
def test_prompt_create_rejects_invalid_metadata(field: str, value: str) -> None:
    data = {
        "name": "Support Answer",
        "slug": "support-answer",
        "initial_version": {"user_prompt_template": "Answer {{question}}."},
    }
    data[field] = value

    with pytest.raises(ValidationError):
        PromptCreate.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_prompt_template", ""),
        ("variables", ["invalid-variable"]),
        ("variables", ["question", "question"]),
    ],
)
def test_prompt_version_rejects_invalid_data(field: str, value: object) -> None:
    data: dict[str, object] = {
        "user_prompt_template": "Answer {{question}}.",
        "variables": ["question"],
    }
    data[field] = value

    with pytest.raises(ValidationError):
        PromptVersionCreate.model_validate(data)
