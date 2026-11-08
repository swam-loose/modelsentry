from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.schemas.prompt import PromptCreate, PromptVersionCreate
from app.services.prompt_registry import (
    PromptRegistryConflictError,
    PromptRegistryNotFoundError,
    PromptRegistryService,
)


def make_payload() -> PromptCreate:
    return PromptCreate(
        name="Support Answer",
        slug="support-answer",
        initial_version=PromptVersionCreate(
            user_prompt_template="Answer {{question}}.",
            variables=["question"],
        ),
    )


def test_service_rejects_duplicate_prompt_slug(db_session: Session) -> None:
    service = PromptRegistryService(db_session)
    service.create_prompt(make_payload())

    with pytest.raises(PromptRegistryConflictError):
        service.create_prompt(make_payload())


def test_service_creates_and_returns_prompt_versions(db_session: Session) -> None:
    service = PromptRegistryService(db_session)
    prompt = service.create_prompt(make_payload())

    created = service.create_version(
        prompt.id,
        PromptVersionCreate(
            user_prompt_template="Answer {{question}} concisely.",
            variables=["question"],
        ),
    )

    assert created.version == 2
    assert service.get_version(prompt.id, 2) is created
    assert len(service.list_versions(prompt.id)) == 2


def test_service_reports_missing_prompt_and_version(db_session: Session) -> None:
    service = PromptRegistryService(db_session)
    unknown_id = UUID("00000000-0000-0000-0000-000000000000")

    with pytest.raises(PromptRegistryNotFoundError):
        service.get_prompt(unknown_id)

    prompt = service.create_prompt(make_payload())
    with pytest.raises(PromptRegistryNotFoundError):
        service.get_version(prompt.id, 99)
