from sqlalchemy.orm import Session

from app.repositories.model_registry import ModelRegistryRepository
from app.schemas.model import RegisteredModelCreate


def test_repository_creates_retrieves_and_lists_models(db_session: Session) -> None:
    repository = ModelRegistryRepository(db_session)
    payload = RegisteredModelCreate(
        name="Mock Evaluator",
        slug="mock-evaluator",
        provider="mock",
        model_identifier="deterministic-v1",
    )

    created = repository.create(payload)

    assert created.id is not None
    assert repository.get_by_id(created.id) is created
    assert repository.get_by_slug("mock-evaluator") is created
    assert repository.get_by_provider_identifier("mock", "deterministic-v1") is created
    assert repository.list_all() == [created]
