from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.schemas.model import RegisteredModelCreate
from app.services.model_registry import (
    ModelRegistryConflictError,
    ModelRegistryNotFoundError,
    ModelRegistryService,
)


def make_payload(
    *,
    slug: str = "mock-evaluator",
    model_identifier: str = "deterministic-v1",
) -> RegisteredModelCreate:
    return RegisteredModelCreate(
        name="Mock Evaluator",
        slug=slug,
        provider="mock",
        model_identifier=model_identifier,
    )


def test_service_rejects_duplicate_slug(db_session: Session) -> None:
    service = ModelRegistryService(db_session)
    service.create(make_payload())

    with pytest.raises(ModelRegistryConflictError):
        service.create(make_payload(model_identifier="deterministic-v2"))


def test_service_rejects_duplicate_provider_identifier(db_session: Session) -> None:
    service = ModelRegistryService(db_session)
    service.create(make_payload())

    with pytest.raises(ModelRegistryConflictError):
        service.create(make_payload(slug="another-mock"))


def test_service_reports_missing_model(db_session: Session) -> None:
    service = ModelRegistryService(db_session)

    with pytest.raises(ModelRegistryNotFoundError):
        service.get_model(UUID("00000000-0000-0000-0000-000000000000"))
