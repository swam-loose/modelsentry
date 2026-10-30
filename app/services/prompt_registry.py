from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.prompt import Prompt, PromptVersion
from app.repositories.prompt_registry import PromptRegistryRepository
from app.schemas.prompt import PromptCreate, PromptVersionCreate


class PromptRegistryConflictError(Exception):
    """Raised when prompt registry uniqueness is violated."""


class PromptRegistryNotFoundError(Exception):
    """Raised when a requested prompt or version does not exist."""


class PromptRegistryService:
    """Apply prompt versioning rules before persistence."""

    def __init__(self, session: Session) -> None:
        self.repository = PromptRegistryRepository(session)

    def create_prompt(self, payload: PromptCreate) -> Prompt:
        if self.repository.get_by_slug(payload.slug) is not None:
            raise PromptRegistryConflictError(
                f"A prompt with slug '{payload.slug}' is already registered."
            )
        try:
            return self.repository.create(payload)
        except IntegrityError as error:
            raise PromptRegistryConflictError(
                "The prompt conflicts with an existing registry entry."
            ) from error

    def get_prompt(self, prompt_id: UUID) -> Prompt:
        prompt = self.repository.get_by_id(prompt_id)
        if prompt is None:
            raise PromptRegistryNotFoundError(f"Prompt '{prompt_id}' was not found.")
        return prompt

    def list_prompts(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Prompt]:
        return self.repository.list_all(offset=offset, limit=limit)

    def create_version(
        self,
        prompt_id: UUID,
        payload: PromptVersionCreate,
    ) -> PromptVersion:
        self.get_prompt(prompt_id)
        try:
            return self.repository.create_version(prompt_id, payload)
        except IntegrityError as error:
            raise PromptRegistryConflictError(
                "The prompt version conflicts with an existing version."
            ) from error

    def list_versions(self, prompt_id: UUID) -> list[PromptVersion]:
        self.get_prompt(prompt_id)
        return self.repository.list_versions(prompt_id)

    def get_version(self, prompt_id: UUID, version: int) -> PromptVersion:
        self.get_prompt(prompt_id)
        prompt_version = self.repository.get_version(prompt_id, version)
        if prompt_version is None:
            raise PromptRegistryNotFoundError(
                f"Version {version} of prompt '{prompt_id}' was not found."
            )
        return prompt_version
