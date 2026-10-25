from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.registered_model import RegisteredModel
from app.repositories.model_registry import ModelRegistryRepository
from app.schemas.model import RegisteredModelCreate


class ModelRegistryConflictError(Exception):
    """Raised when a model conflicts with an existing registry entry."""


class ModelRegistryNotFoundError(Exception):
    """Raised when a requested model does not exist."""


class ModelRegistryService:
    """Apply registry rules before persistence."""

    def __init__(self, session: Session) -> None:
        self.repository = ModelRegistryRepository(session)

    def create(self, payload: RegisteredModelCreate) -> RegisteredModel:
        if self.repository.get_by_slug(payload.slug) is not None:
            raise ModelRegistryConflictError(
                f"A model with slug '{payload.slug}' is already registered."
            )
        existing_endpoint = self.repository.get_by_provider_identifier(
            payload.provider,
            payload.model_identifier,
        )
        if existing_endpoint is not None:
            raise ModelRegistryConflictError(
                "This provider and model identifier are already registered."
            )
        try:
            return self.repository.create(payload)
        except IntegrityError as error:
            raise ModelRegistryConflictError(
                "The model conflicts with an existing registry entry."
            ) from error

    def get_model(self, model_id: UUID) -> RegisteredModel:
        model = self.repository.get_by_id(model_id)
        if model is None:
            raise ModelRegistryNotFoundError(
                f"Registered model '{model_id}' was not found."
            )
        return model

    def list_models(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[RegisteredModel]:
        return self.repository.list_all(offset=offset, limit=limit)
