# ModelSentry

**Evaluate every model. Govern every release.**

ModelSentry is an open-source AI evaluation and governance platform focused on
reproducible test datasets, deterministic evaluators, human review, release
comparison, and evidence-backed quality gates.

## Current scope

Version 0.1 starts as a Windows-native FastAPI application with SQLite and a
mock model provider. It does not require Docker, WSL, Redis, PostgreSQL, or a
paid AI API.

The current API includes model registration, immutable prompt versions, and
versioned evaluation datasets with deterministic JSONL content hashes.

## Requirements

- Python 3.12
- Git
- Visual Studio Code (recommended)

## Local setup

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --editable ".[dev]"
python -m alembic upgrade head
```

## Run the API

```powershell
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

## Database migrations

Apply all pending migrations:

```powershell
python -m alembic upgrade head
```

Roll back the latest migration:

```powershell
python -m alembic downgrade -1
```

## Evaluation dataset JSONL

Each non-empty line must contain one JSON object with a unique `case_key`, an
`input` object, and optional `expected_output` and `metadata` values:

```json
{"case_key":"capital-france","input":{"question":"What is the capital of France?"},"expected_output":{"contains":"Paris"},"metadata":{"category":"geography"}}
```

Import JSONL through `POST /api/v1/datasets/{dataset_id}/versions/jsonl` using
the `application/x-ndjson` content type. Equivalent validated content produces
the same SHA-256 hash and cannot be registered twice for the same dataset.

## Quality checks

```powershell
python -m ruff check app tests migrations
python -m ruff format --check app tests migrations
python -m pytest --cov=app --cov-report=term-missing
```

## Initial roadmap

1. Model and prompt registry
2. Versioned JSONL evaluation datasets
3. Mock-provider evaluation runs
4. Deterministic schema and policy evaluators
5. Human review and approval workflow
6. A/B comparison, latency, and cost metrics
7. Evidence-backed release quality gates
