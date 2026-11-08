from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

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
    assert {
        "api_keys",
        "evaluation_cases",
        "evaluation_checks",
        "evaluation_dataset_versions",
        "evaluation_datasets",
        "evaluation_results",
        "evaluation_runs",
        "human_reviews",
        "prompt_versions",
        "prompts",
        "registered_models",
        "release_gate_checks",
        "release_gate_evaluations",
        "release_gate_versions",
        "release_gates",
        "user_accounts",
    } <= table_names
    run_columns = {
        column["name"] for column in inspect(engine).get_columns("evaluation_runs")
    }
    assert {
        "average_latency_ms",
        "estimated_cost_usd",
        "input_tokens",
        "output_tokens",
        "p95_latency_ms",
        "total_latency_ms",
    } <= run_columns
    engine.dispose()
    command.check(config)
    command.downgrade(config, "base")
    engine = create_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    finally:
        engine.dispose()


def test_security_migration_preserves_existing_users_and_api_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_url = "sqlite+pysqlite:///" + (tmp_path / "legacy.db").as_posix()
    monkeypatch.setenv("MODELSENTRY_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(Path(__file__).parents[1] / "alembic.ini")
    command.upgrade(config, "0009_authentication_rbac")
    user_id, key_id = uuid4().hex, uuid4().hex
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO user_accounts (id, email, display_name, role) "
                "VALUES (:id, 'legacy@example.com', 'Legacy Admin', 'admin')"
            ),
            {"id": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO api_keys (id, user_id, label, key_prefix, key_hash) "
                "VALUES (:id, :user_id, 'Legacy key', 'msk_legacy', :key_hash)"
            ),
            {"id": key_id, "user_id": user_id, "key_hash": "f" * 64},
        )
    engine.dispose()

    command.upgrade(config, "head")
    command.check(config)
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT bootstrap_slot FROM user_accounts")
            ).scalar()
            is None
        )
        assert (
            connection.execute(text("SELECT key_hash FROM api_keys")).scalar()
            == "f" * 64
        )
        assert "decided_by_user_id" in {
            column["name"]
            for column in inspect(connection).get_columns("human_reviews")
        }
    engine.dispose()

    command.downgrade(config, "0009_authentication_rbac")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT email FROM user_accounts")).scalar()
            == "legacy@example.com"
        )
        assert connection.execute(text("SELECT COUNT(*) FROM api_keys")).scalar() == 1
    engine.dispose()
    command.upgrade(config, "head")
    command.check(config)
