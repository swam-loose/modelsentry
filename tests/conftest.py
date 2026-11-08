import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.main import create_app

TEST_BOOTSTRAP_TOKEN = "test-bootstrap-token-with-sufficient-entropy"
TEST_API_KEY_PEPPER = "test-api-key-pepper-with-sufficient-entropy"


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    for variable in os.environ:
        if variable.upper().startswith("MODELSENTRY_"):
            monkeypatch.delenv(variable)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    database_path = (tmp_path / "repository.db").as_posix()
    engine = create_db_engine(f"sqlite+pysqlite:///{database_path}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    database_path = (tmp_path / "api.db").as_posix()
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("MODELSENTRY_BOOTSTRAP_TOKEN", TEST_BOOTSTRAP_TOKEN)
    monkeypatch.setenv("MODELSENTRY_API_KEY_PEPPER", TEST_API_KEY_PEPPER)
    get_settings.cache_clear()
    engine = create_db_engine(database_url)
    Base.metadata.create_all(engine)
    application = create_app(
        database_url=database_url,
    )
    with TestClient(application) as test_client:
        response = test_client.post(
            "/api/v1/auth/bootstrap",
            headers={"X-Bootstrap-Token": TEST_BOOTSTRAP_TOKEN},
            json={
                "email": "admin@example.com",
                "display_name": "Test Administrator",
            },
        )
        assert response.status_code == 201
        test_client.headers.update(
            {"Authorization": (f"Bearer {response.json()['credential']['api_key']}")}
        )
        yield test_client
    Base.metadata.drop_all(engine)
    engine.dispose()
