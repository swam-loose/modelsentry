# ModelSentry

[![CI](https://github.com/swam-loose/modelsentry/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/swam-loose/modelsentry/actions/workflows/ci.yml)

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
cost, baseline-versus-candidate comparisons, and immutable release-gate
decisions. Local API-key authentication and role-based authorization protect
all product resources while keeping the health endpoint public.

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

Create a local `.env` from `.env.example` and replace both documented secret
placeholders. `MODELSENTRY_API_KEY_PEPPER` protects stored API-key digests and
must remain stable for existing keys to work. `MODELSENTRY_BOOTSTRAP_TOKEN`
authorizes only the first administrator bootstrap. Production startup requires
independent random secrets of at least 32 characters and rejects empty values
and documented placeholders. Remove the bootstrap token after setup and restart.

## Run the API

```powershell
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

## Authentication and role-based access control

After applying migrations, create the first administrator exactly once through
`POST /api/v1/auth/bootstrap`, supplying `X-Bootstrap-Token`. The response
contains an `msk_...` bearer API key exactly once. Store it securely and send
it on protected requests as `Authorization: Bearer <api-key>`.

```powershell
$headers = @{"X-Bootstrap-Token"=$env:MODELSENTRY_BOOTSTRAP_TOKEN}; $body = '{"email":"admin@example.com","display_name":"Administrator"}'; $bootstrap = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/auth/bootstrap" -Headers $headers -ContentType "application/json" -Body $body; $apiKey = $bootstrap.credential.api_key
```

ModelSentry stores only an HMAC-SHA-256 digest and a non-secret key prefix.
Administrators can register identities, issue expiring credentials, inspect
credential metadata, and revoke keys. Revocation is irreversible; audit
metadata remains available, while raw keys and digests are never returned by
list endpoints.

| Role | Effective access |
| --- | --- |
| `admin` | Identity administration and all product operations |
| `operator` | Read access and product operations, excluding review decisions |
| `reviewer` | Read access and final decisions on their own review assignments |
| `viewer` | Read-only access |

Use `GET /api/v1/auth/me` to inspect the authenticated user, credential ID,
role, and effective permission labels. ModelSentry v0.1 deliberately uses
local API keys rather than passwords or an external identity provider; OAuth,
SSO, and organization-level identity federation remain future integrations.

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

The API binds reviewer decisions to the authenticated account's normalized
email. An administrator may override an assignment, but `decided_by_user_id`
records the actual actor separately from the assigned reviewer. Legacy reviews
keep a null actor ID because the application cannot reconstruct old identities.
These are administrator-managed local accounts, not proof of legal identity or
email ownership. See [SECURITY.md](SECURITY.md) for deployment limits.

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

## Evidence-backed release quality gates

Register a gate through `POST /api/v1/release-gates`. Every gate begins with an
immutable policy version and can receive new versions without rewriting prior
criteria. Policies can enforce a minimum pass rate, a maximum error count,
optional average and p95 latency limits, an optional estimated-cost limit,
human approval, and no deterministic quality regression against a baseline.

Evaluate a completed candidate through `POST
/api/v1/release-gates/{gate_id}/evaluations`. ModelSentry snapshots the latest
policy version, candidate run, optional baseline run, final `passed` or
`failed` status, and an ordered expected-versus-actual evidence record for
every configured check. Historical decisions therefore remain reproducible
when a gate later receives stricter or looser criteria.

The default policy is intentionally conservative: 100% pass rate, zero
errored cases, human approval, and no quality regression. A gate decision is a
governance artifact only; ModelSentry never deploys, promotes, or rolls back a
model automatically.

## Quality checks

```powershell
python -m ruff check app tests migrations scripts
python -m ruff format --check app tests migrations scripts
python -m pytest -p no:cacheprovider --cov=app --cov-report=term-missing
python scripts/check_release.py migrations
```

## CI and release candidates

The `CI` workflow runs on pull requests to `develop` and `main`, pushes to
those branches, and manual dispatch. Python 3.12 tests run on Windows and
Linux with a minimum application coverage of 95%. It also checks migrations,
builds a wheel and source distribution, validates their metadata and contents,
and smoke-tests the installed wheel outside the checkout.

Workflow actions are pinned to immutable SHAs, repository permissions are
read-only, and candidate artifacts contain no runtime database or real `.env`.
Nothing is published, tagged, or deployed automatically. Follow the
[release checklist](docs/RELEASE_CHECKLIST.md) before approving version 0.1.0.
The checklist includes an explicit software-license decision; no license is
chosen on the maintainer's behalf.

## Version 0.1 roadmap

1. Model and prompt registry — complete
2. Versioned JSONL evaluation datasets — complete
3. A/B comparison, latency, and cost metrics — complete
4. Evidence-backed release quality gates — complete
5. Authentication and role-based access control — complete

Version 0.1 now provides an end-to-end local evaluation and governance path.
Future milestones can add an Ollama adapter, asynchronous execution,
organization isolation, and external identity-provider integration. Version
0.1.0 remains a release candidate until the checklist is approved and the
exact release commit passes CI.
