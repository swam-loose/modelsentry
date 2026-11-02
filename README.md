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
reproducible evaluation runs powered by a local mock provider. Runs expose
deterministic evaluator evidence, human review state, usage metrics, estimated
cost, and baseline-versus-candidate comparisons.

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

## Human review and approval

Completed runs can be assigned to human reviewers through `POST
/api/v1/reviews`. The review queue supports filtering by run, reviewer, and
status. A reviewer submits one final `approved` or `rejected` decision through
`PATCH /api/v1/reviews/{review_id}`; rejections require a rationale and decided
reviews cannot be rewritten.

Run responses expose a conservative aggregate approval status. Any rejection
marks the run as rejected, pending assignments block approval, and only runs
whose requested reviews are all approved become approved. Automated evaluator
results never create a human approval decision.

Version 0.1 records reviewer identifiers supplied by the API caller. Identity
authentication and role-based authorization remain explicit roadmap items, so
the local workflow is auditable but must not yet be treated as proof of a
reviewer's real-world identity.

## A/B run comparisons and cost evidence

Registering a model accepts optional `input_cost_per_million` and
`output_cost_per_million` USD rates. Each run snapshots those rates so that
historical cost estimates do not change when registry pricing is updated.
Case and run responses expose input/output tokens, estimated cost, total and
average latency, and p95 latency.

The local mock provider estimates token usage deterministically from UTF-8
content; `token_usage_estimated` makes that limitation explicit. Future remote
provider adapters should persist provider-reported usage instead.

Compare two completed runs through `POST /api/v1/run-comparisons` with
`baseline_run_id` and `candidate_run_id`. Both runs must use the same immutable
dataset version. The response aligns cases by ID and reports quality,
performance, token, latency, and cost deltas with `improved`, `regressed`,
`mixed`, `unchanged`, or `inconclusive` outcomes.

Comparison outcomes are evidence summaries, not release approvals. ModelSentry
does not promote a candidate automatically; deterministic checks and human
review remain separately visible.

## Quality checks

```powershell
python -m ruff check app tests migrations
python -m ruff format --check app tests migrations
python -m pytest --cov=app --cov-report=term-missing
```

## Initial roadmap

1. Model and prompt registry — complete
2. Versioned JSONL evaluation datasets — complete
3. A/B comparison, latency, and cost metrics — complete
4. Evidence-backed release quality gates — next
5. Authentication and role-based access control
