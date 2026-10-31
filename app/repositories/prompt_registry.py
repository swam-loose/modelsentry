from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.prompt import Prompt, PromptVersion
from app.schemas.prompt import PromptCreate, PromptVersionCreate


class PromptRegistryRepository:
    """Persist prompts and their immutable versions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: PromptCreate) -> Prompt:
        prompt = Prompt(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
        )
        prompt.versions.append(
            PromptVersion(
                version=1,
                **payload.initial_version.model_dump(),
            )
        )
        self.session.add(prompt)
        self._commit()
        self.session.refresh(prompt)
        return prompt

    def create_version(
        self,
        prompt_id: UUID,
        payload: PromptVersionCreate,
    ) -> PromptVersion:
        version = PromptVersion(
            prompt_id=prompt_id,
            version=self.get_latest_version_number(prompt_id) + 1,
            **payload.model_dump(),
        )
        self.session.add(version)
        self._commit()
        self.session.refresh(version)
        return version

    def get_by_id(self, prompt_id: UUID) -> Prompt | None:
        statement = (
            select(Prompt)
            .where(Prompt.id == prompt_id)
            .options(selectinload(Prompt.versions))
        )
        return self.session.scalar(statement)

    def get_by_slug(self, slug: str) -> Prompt | None:
        statement = select(Prompt).where(Prompt.slug == slug)
        return self.session.scalar(statement)

    def list_all(self, *, offset: int = 0, limit: int = 100) -> list[Prompt]:
        statement = (
            select(Prompt)
            .order_by(Prompt.created_at, Prompt.id)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def list_versions(self, prompt_id: UUID) -> list[PromptVersion]:
        statement = (
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.version)
        )
        return list(self.session.scalars(statement))

    def get_version(
        self,
        prompt_id: UUID,
        version: int,
    ) -> PromptVersion | None:
        statement = select(PromptVersion).where(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.version == version,
        )
        return self.session.scalar(statement)

    def get_latest_version_number(self, prompt_id: UUID) -> int:
        statement = select(func.max(PromptVersion.version)).where(
            PromptVersion.prompt_id == prompt_id
        )
        return self.session.scalar(statement) or 0

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
