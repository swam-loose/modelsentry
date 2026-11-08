# API guide

[README](../README.md) · [Getting started](GETTING_STARTED.md) · [Synthetic demo](SYNTHETIC_DEMO.md)

This walkthrough assumes a running local API at `http://127.0.0.1:8000`, the
default `/api/v1` prefix, and a migrated database. JSON blocks are **HTTP request
bodies**: paste them into Swagger UI or your API client, not directly into a
PowerShell terminal. Replace UUID placeholders with the actual response IDs.

## Authentication

### Create the first administrator

Open `/docs`, expand `POST /api/v1/auth/bootstrap`, and choose **Try it out**.
Supply the configured bootstrap secret in `X-Bootstrap-Token`, with this body:

```json
{"email":"admin@example.com","display_name":"Local Administrator"}
```

Expected result: **HTTP 201**, containing `user` and `credential`. Save
`credential.api_key` securely; the API returns it only once. Never post that
response in an issue or include it in a public screenshot.

Select **Authorize** in Swagger and enter the raw `msk_...` API key. The bearer
scheme adds the `Bearer` prefix. Confirm access with `GET /api/v1/auth/me`.
Do not use the bootstrap token as your bearer key.

Bootstrap requires a configured token and a database with no user accounts.
Repeating it returns HTTP 409. After success, remove the bootstrap setting
from `.env`, restart the server, and keep the key pepper unchanged.

<details>
<summary><strong>PowerShell alternative — correctly reads a token configured in .env</strong></summary>

Open a second PowerShell terminal in the project root while the server runs.
These lines capture secrets in variables instead of printing them:

```powershell
$bootstrapToken = & ".\.venv\Scripts\python.exe" -c "from app.core.config import get_settings; token=get_settings().bootstrap_token; assert token is not None, 'Bootstrap token is not configured'; print(token.get_secret_value())"
$admin = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/auth/bootstrap" -Headers @{"X-Bootstrap-Token"=$bootstrapToken} -ContentType "application/json" -Body '{"email":"admin@example.com","display_name":"Local Administrator"}'
$headers = @{Authorization = "Bearer $($admin.credential.api_key)"}
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/v1/auth/me" -Headers $headers | Select-Object -ExpandProperty user
```

Store the one-time key in a suitable secret store before closing the session.
Do not display `$admin` or `$bootstrapToken` in shared terminal recordings.
If you already bootstrapped the application, use an existing issued key rather
than executing bootstrap again.

</details>

### Roles and credentials

Only administrators manage local users and issue/revoke credentials. Create a
reviewer through `POST /api/v1/auth/users`:

```json
{"email":"reviewer@example.com","display_name":"Local Reviewer","role":"reviewer"}
```

Issue that user a key through `POST /api/v1/auth/users/{user_id}/api-keys`:

```json
{"label":"local-review-session"}
```

`expires_at` is optional and must be a future timestamp if supplied. Prefer
short-lived credentials when appropriate. The raw key appears only in the
issuance response; list endpoints expose metadata, not the key or its digest.
`DELETE /api/v1/auth/api-keys/{api_key_id}` revokes a key irreversibly and keeps
its audit metadata. Local accounts are not email-verification or SSO accounts.

## Create the inputs

Use the administrator or an operator key for product creation.

### 1. Register a mock model

`POST /api/v1/models`:

```json
{
  "name": "Local Demo Model",
  "slug": "local-demo-model",
  "provider": "mock",
  "model_identifier": "demo-v1",
  "input_cost_per_million": "0.50",
  "output_cost_per_million": "1.50"
}
```

Save the returned `id`. Rates here are invented demonstration values, not
provider prices. Registering an `ollama` provider identifier does not make an
Ollama execution adapter available in v0.1; use `mock` for this walkthrough.

### 2. Create a prompt and its first version

`POST /api/v1/prompts`:

```json
{
  "name": "Local Support Prompt",
  "slug": "local-support-prompt",
  "initial_version": {
    "user_prompt_template": "Question: {{question}}",
    "variables": ["question"],
    "change_note": "Initial synthetic walkthrough."
  }
}
```

The response contains prompt metadata and `versions`. Save `versions[0].id`
as the **prompt version ID**, not the parent prompt ID. To change a template,
create a new version with `POST /api/v1/prompts/{prompt_id}/versions`.

### 3. Register a dataset and a version

`POST /api/v1/datasets`:

```json
{"name":"Local Support Cases","slug":"local-support-cases","description":"Synthetic rule-execution example."}
```

Save its `id`, then send this body to
`POST /api/v1/datasets/{dataset_id}/versions`:

```json
{
  "change_note": "One controlled synthetic case.",
  "cases": [
    {
      "case_key": "password-reset-policy",
      "input": {
        "question": "How can I reset my password?",
        "mock_response": "Use the official password reset link."
      },
      "expected_output": {
        "mode": "all",
        "evaluators": [
          {"type": "required_terms", "terms": ["reset link"]},
          {"type": "forbidden_terms", "terms": ["share your password"]}
        ]
      },
      "metadata": {"synthetic": true}
    }
  ]
}
```

Save the returned **dataset version ID**. The response also exposes
`content_sha256` and `case_count`. Reimporting identical validated content for
the same dataset is rejected rather than silently creating a duplicate version.

For JSONL, use `POST /api/v1/datasets/{dataset_id}/versions/jsonl` with a raw
UTF-8 `application/x-ndjson` body, not a multipart form. Each non-empty line
must be one complete case object with a unique `case_key`:

```jsonl
{"case_key":"paris","input":{"question":"Name the capital of France.","mock_response":"Paris"},"expected_output":{"contains":"Paris"},"metadata":{"synthetic":true}}
```

The mock response is fixture data controlled by the caller. Without
`input.mock_response`, the provider returns its model marker and rendered user
prompt; it does not infer a real answer to the question.

## Execute a run

`POST /api/v1/runs`:

```json
{
  "registered_model_id": "<model UUID>",
  "prompt_version_id": "<prompt-version UUID>",
  "dataset_version_id": "<dataset-version UUID>"
}
```

The v0.1 mock run executes **synchronously** and returns HTTP 201 with the run
and case evidence. Inspect it again with `GET /api/v1/runs/{run_id}`.

| Field | Meaning |
| --- | --- |
| `status` | Execution lifecycle; `completed` does not mean all quality checks passed |
| `results[].status` | Provider success/error for that case |
| `results[].evaluation_status` | Deterministic quality outcome |
| `results[].checks` | Evaluator type, expected value, actual evidence, message, and decision |
| `passed_cases` / `failed_cases` / `errored_cases` | Distinguish quality failures from execution errors |
| `pass_rate` | Aggregate deterministic pass rate, when evaluated |
| `approval_status` | Human review state; not created by a passing evaluator |
| `token_usage_estimated` | Explicitly marks synthetic token/cost accounting |

The evaluator vocabulary is `exact_match`, `contains`, `json_equals`,
`json_schema`, `required_terms`, and `forbidden_terms`. JSON Schema checks use
Draft 2020-12; their request field is `schema`. Policies accept `all` or `any`
composition. Literal expected strings and documented shorthand forms are also
supported, but explicit policies are easier to inspect.

## Compare runs

Create two runs using the same immutable dataset version. Then send
`POST /api/v1/run-comparisons`:

```json
{"baseline_run_id":"<baseline-run UUID>","candidate_run_id":"<candidate-run UUID>"}
```

Expected result: HTTP 200 with aligned cases and quality, usage, cost, and
latency deltas. Outcomes may be improved, regressed, mixed, unchanged, or
inconclusive. A comparison summarizes evidence; it does not approve a release.

When `mock_response` is explicitly set, it controls the output regardless of
the prompt. For an actual synthetic regression driven by different prompt
versions, run the [complete demo](SYNTHETIC_DEMO.md), which selects safe and
unsafe fixture replies through its versioned templates.

## Human review

An administrator or operator assigns a completed run through
`POST /api/v1/reviews`:

```json
{"run_id":"<candidate-run UUID>","reviewer":"reviewer@example.com","reviewer_role":"local-reviewer"}
```

Use the **assigned reviewer's own key** to submit
`PATCH /api/v1/reviews/{review_id}`:

```json
{"decision":"approved","rationale":"Reviewed the configured checks for this synthetic case."}
```

For rejection, use `decision: "rejected"` and provide a rationale. A final
review cannot be rewritten. An unrelated reviewer receives HTTP 403.
Administrators can override assignments, but `decided_by_user_id` records
that administrator, not the assigned reviewer.

Pending assignments block aggregate approval; any rejection rejects the run;
only a set of fully approved requested reviews produces an approved state.
Do not represent a test-script decision as a real person's assessment.

## Release gates

Create a policy with `POST /api/v1/release-gates`:

```json
{
  "name": "Local Release Policy",
  "slug": "local-release-policy",
  "initial_version": {
    "min_pass_rate": "1.0",
    "max_errored_cases": 0,
    "require_human_approval": true,
    "require_no_quality_regressions": true
  }
}
```

Optional criteria are `max_average_latency_ms`, `max_p95_latency_ms`, and
`max_estimated_cost_usd`. Add a new policy with
`POST /api/v1/release-gates/{gate_id}/versions` rather than rewriting old criteria.

Evaluate through `POST /api/v1/release-gates/{gate_id}/evaluations`:

```json
{"baseline_run_id":"<baseline-run UUID>","candidate_run_id":"<candidate-run UUID>"}
```

Expected result: HTTP 201 containing `status`, the policy-version reference,
run references, and ordered `checks`. A failed gate evaluation is a successful
recording of a blocked decision, not necessarily an HTTP error. Read it later
at `GET /api/v1/release-gate-evaluations/{evaluation_id}`.

A later review or policy change does not revise an earlier evaluation. To
observe the updated candidate state, create a **new** evaluation. No gate
operation deploys, promotes, or rolls back a model.

## Common responses

| Status | Interpretation |
| --- | --- |
| 200 | Successful read or comparison |
| 201 | Resource, run, review, version, or gate evaluation recorded |
| 204 | API key revoked |
| 401 | Missing, invalid, expired, or revoked credential |
| 403 | Role or reviewer assignment forbids the action |
| 404 | Referenced resource was not found |
| 409 | State conflict, duplicate content, repeated bootstrap, or invalid comparison context |
| 413 | JSONL content exceeds the accepted limit |
| 422 | Invalid request, unsupported execution provider, or evaluator policy |

See `/docs` for the generated schema and exact field constraints. Use only
synthetic data in public reproductions and follow [SECURITY.md](../SECURITY.md).
