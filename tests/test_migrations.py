from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings


def test_migrations_upgrade_and_downgrade(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).parents[1]
    database_path = (tmp_path / "migration.db").as_posix()
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("MODELSENTRY_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(project_root / "alembic.ini")

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    table_names = set(inspect(engine).get_table_names())
    assert {"prompt_versions", "prompts", "registered_models"} <= table_names
    engine.dispose()

    command.downgrade(config, "base")

    engine = create_engine(database_url)
    table_names = set(inspect(engine).get_table_names())
    assert not {"prompt_versions", "prompts", "registered_models"} & table_names
    engine.dispose()
