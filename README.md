# ModelSentry

**Evaluate every model. Govern every release.**

ModelSentry is an open-source AI evaluation and governance platform focused on
reproducible test datasets, deterministic evaluators, human review, release
comparison, and evidence-backed quality gates.

## Current scope

Version 0.1 starts as a Windows-native FastAPI application with SQLite and a
mock model provider. It does not require Docker, WSL, Redis, PostgreSQL, or a
paid AI API.

The current API includes model registration, immutable prompt versions,
versioned evaluation datasets with deterministic JSONL content hashes, and
reproducible evaluation runs powered by a local mock provider.

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

## Deterministic mock evaluation runs

Create a run through `POST /api/v1/runs` using the IDs of a registered model,
an immutable prompt version, and an evaluation dataset version. The first
provider is `mock`: it renders every case locally, records case-level outputs
and errors, and produces deterministic latency values for reproducible tests.

The mock provider requires no credentials, external service, or paid API. A
case can define `input.mock_response` to control its exact synthetic output.
Run details and evidence are available through `GET /api/v1/runs/{run_id}`.

## Deterministic evaluators

Each evaluation case can define an `expected_output` policy. ModelSentry
supports exact text matching, substring checks, structural JSON equality,
Draft 2020-12 JSON Schema validation, required terms, and forbidden terms.
Checks are deterministic, persisted individually, and combined with either
`all` or `any` semantics.

```json
{
  "mode": "all",
  "evaluators": [
    {"type": "contains", "value": "Paris", "case_sensitive": false},
    {"type": "forbidden_terms", "terms": ["uncertain", "London"]}
  ]
}
```

For compatibility, concise forms such as `{"contains":"Paris"}` remain
valid. Run responses expose every evaluator decision, its expected and actual
evidence, case-level status, aggregate passed and failed counts, and pass rate.

## Quality checks

```powershell
python -m ruff check app tests migrations
python -m ruff format --check app tests migrations
python -m pytest --cov=app --cov-report=term-missing
```

## Initial roadmap

1. Model and prompt registry
2. Versioned JSONL evaluation datasets
3. Human review and approval workflow
4. A/B comparison, latency, and cost metrics
5. Evidence-backed release quality gates

