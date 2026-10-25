from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.registered_model import RegisteredModel
from app.schemas.model import RegisteredModelCreate


class ModelRegistryRepository:
    """Persist and query registered evaluation models."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: RegisteredModelCreate) -> RegisteredModel:
        model = RegisteredModel(**payload.model_dump())
        self.session.add(model)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        self.session.refresh(model)
        return model

    def get_by_id(self, model_id: UUID) -> RegisteredModel | None:
        return self.session.get(RegisteredModel, model_id)

    def get_by_slug(self, slug: str) -> RegisteredModel | None:
        statement = select(RegisteredModel).where(RegisteredModel.slug == slug)
        return self.session.scalar(statement)

    def get_by_provider_identifier(
        self,
        provider: str,
        model_identifier: str,
    ) -> RegisteredModel | None:
        statement = select(RegisteredModel).where(
            RegisteredModel.provider == provider,
            RegisteredModel.model_identifier == model_identifier,
        )
        return self.session.scalar(statement)

    def list_all(self, *, offset: int = 0, limit: int = 100) -> list[RegisteredModel]:
        statement = (
            select(RegisteredModel)
            .order_by(RegisteredModel.created_at, RegisteredModel.id)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))
