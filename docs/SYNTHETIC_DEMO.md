# Synthetic end-to-end demo

This demo exercises the real FastAPI routes, authentication, migrations,
repositories, deterministic evaluators, comparisons, reviews, and release gates.
It runs in-process through `TestClient`; it does not need a running server.

Everything is synthetic. The mock provider echoes fixture text selected by a
versioned template; it does not call or measure a real language model. Reviewer
approval is explicitly simulated by the test, not granted by a real person.
A passing demo is not permission to publish ModelSentry or deploy a model.

## Run on Windows

From the repository root, with development dependencies installed, run this
single PowerShell line. Activation is optional because the interpreter path is
explicit:

```powershell
$testTemp = Join-Path $env:LOCALAPPDATA ("ModelSentry\pytest-demo-" + [guid]::NewGuid().ToString("N")); New-Item -ItemType Directory -Force -Path $testTemp | Out-Null; & ".\.venv\Scripts\python.exe" -m pytest tests/test_synthetic_demo.py "--basetemp=$testTemp" -p "no:cacheprovider" -q -s
```

On Linux, use the same virtual environment with:

```bash
.venv/bin/python -m pytest tests/test_synthetic_demo.py -p no:cacheprovider -q -s
```

## What it demonstrates

| Scenario | Expected evidence |
| --- | --- |
| Public health and protected product API | HTTP 200 and HTTP 401 |
| Viewer tries to register a model | HTTP 403 |
| Import the same two-case JSONL dataset twice | HTTP 201, then HTTP 409 |
| Prompt version 1: safe synthetic baseline | 2/2 cases pass |
| Prompt version 2: deliberate regression | 0/2 cases pass; two regressions |
| Prompt version 3: restore safe replies | 2/2 cases pass |
| Evaluate the regression | Gate fails on quality and regression checks |
| Evaluate the fixed run before review | Gate fails only on pending approval |
| Unassigned reviewer tries to approve | HTTP 403; assignment stays pending |
| Assigned reviewer submits simulated approval | Actual actor ID is recorded |
| Try to rewrite the final review | HTTP 409 |
| Reevaluate the reviewed fixed run | All gate checks pass |
| Read the earlier gate decision and prompt version | Historical evidence is unchanged |

The two invented support examples test required phrases and forbidden claims:
password reset advice must mention a reset link and must not ask a user to
share a password; refund advice must mention policy and must not promise a
guaranteed refund. These examples illustrate configured checks, not complete
security, customer-service, or model-quality evaluation.

## Isolation and secrets

- The existing autouse test fixture removes application environment overrides
  and changes the working directory to a new pytest temporary directory, so
  the repository's real `.env` is not read during the scenario.
- The demo generates independent random bootstrap and API-key pepper secrets.
  All identities use reserved `example.com` addresses. No key or secret is
  printed in the success report.
- Migrations run only against a fresh `synthetic-demo.db` under the test's
  temporary directory. An existing database at that path is refused.
- No authentication dependency is replaced or bypassed.
- Application shutdown disposes its database connections. The demo removes
  only its own synthetic database afterward; normal runtime data is untouched.
- No external provider, network server, paid API, tag, release, or deployment
  is created. Token counts, latency, and configured cost rates are synthetic
  estimates, not real provider measurements or market prices.

## Completion evidence

Success prints a JSON summary, followed by `SYNTHETIC_DEMO_PASSED` and
`1 passed`. In particular, confirm:

```json
{
  "baseline_pass_rate": 1.0,
  "regressed_pass_rate": 0.0,
  "fixed_pass_rate": 1.0,
  "regression_gate": "failed",
  "unreviewed_fixed_gate": "failed",
  "reviewed_fixed_gate": "passed",
  "unauthorized_reviewer_http": 403,
  "human_review_is_simulated": true,
  "deployment_performed": false
}
```

The complete report also includes deduplication, identity, and history checks.
Synthetic `failed` decisions in that report are expected safeguards, not test
failures. Pytest must exit with code zero. Keep the release checklist unchecked
until the maintainer has run the demo and reviewed its evidence.
