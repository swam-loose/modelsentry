from sqlalchemy.orm import Session

from app.repositories.prompt_registry import PromptRegistryRepository
from app.schemas.prompt import PromptCreate, PromptVersionCreate


def make_payload() -> PromptCreate:
    return PromptCreate(
        name="Support Answer",
        slug="support-answer",
        initial_version=PromptVersionCreate(
            system_prompt="Answer only from supplied evidence.",
            user_prompt_template="Answer {{question}}.",
            variables=["question"],
        ),
    )


def test_repository_creates_prompt_and_sequential_versions(
    db_session: Session,
) -> None:
    repository = PromptRegistryRepository(db_session)

    created = repository.create(make_payload())
    second_version = repository.create_version(
        created.id,
        PromptVersionCreate(
            user_prompt_template="Answer {{question}} concisely.",
            variables=["question"],
            change_note="Require concise answers.",
        ),
    )

    assert created.id is not None
    assert repository.get_by_slug("support-answer") is created
    assert repository.get_by_id(created.id) is created
    assert second_version.version == 2
    assert [version.version for version in repository.list_versions(created.id)] == [
        1,
        2,
    ]
    assert repository.get_version(created.id, 2) is second_version
