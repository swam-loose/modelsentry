# ModelSentry 0.1.0

First local/mock release of ModelSentry, an AI evaluation and governance API
for reproducible tests and evidence-backed release decisions.

## Included

- Model registry, immutable prompt versions, and versioned JSONL datasets with
  content hashes and duplicate-content protection.
- Synchronous deterministic mock runs with case-level evaluator evidence:
  text matching, required/forbidden terms, JSON comparison, and JSON Schema.
- Baseline/candidate comparisons with quality, synthetic latency, estimated
  token usage, and estimated cost deltas.
- Assigned-reviewer decisions with actor attribution, immutable history, and
  versioned release quality gates. Pending review blocks approval; gate
  decisions never deploy or promote a model.
- API-key authentication, roles, expiry, revocation, atomic administrator
  bootstrap, and reviewer-ownership enforcement.
- Ten Alembic migrations, Windows/Linux CI on Python 3.12, a 95% coverage gate,
  package-content checks, and an installed-wheel smoke test.
- An isolated synthetic API demo showing a regression blocked, a fixed run
  awaiting review, an unrelated reviewer denied, and an explicitly simulated
  approval without rewriting earlier evidence.
- MIT licensing, with the license included in both distributions.

## Validation and assets

The release must use the successful main-branch CI run for its exact tagged
commit. The public release body records that commit and run, along with SHA-256
checksums for these CI-built distributions:

- `modelsentry-0.1.0-py3-none-any.whl`
- `modelsentry-0.1.0.tar.gz`
- `SHA256SUMS.txt` (distribution checksums)

The application baseline was validated with 216 passing tests and 95.10%
coverage. Only release documentation changes follow that baseline; the final
commit must independently pass the same complete CI workflow.

## Installation and security

Python 3.12 is required. This version uses local SQLite and requires no Docker,
WSL, Redis, PostgreSQL, or paid model API.

Use the source checkout or source distribution for Alembic migrations. The
wheel contains the runtime Python package and license, not the migration CLI
configuration and history. Apply migrations before using product endpoints;
never run destructive migration tests against a runtime database.

Create independent random bootstrap and API-key pepper secrets as documented.
Keep an existing pepper stable so previously issued keys remain usable. Store
one-time API keys securely and do not expose the service publicly without
additional transport and operational safeguards.

Setup and security references:

- [README](https://github.com/swam-loose/modelsentry/blob/v0.1.0/README.md)
- [Security policy](https://github.com/swam-loose/modelsentry/blob/v0.1.0/SECURITY.md)
- [Synthetic demo](https://github.com/swam-loose/modelsentry/blob/v0.1.0/docs/SYNTHETIC_DEMO.md)
- [MIT license](https://github.com/swam-loose/modelsentry/blob/v0.1.0/LICENSE)

## Known limits

This is a local, single-organization API with a mock provider, not a hosted
service or a production identity platform. It has no real LLM provider adapter,
asynchronous queue, multi-tenancy, external SSO, or graphical dashboard.
Mock outputs, latency, token counts, and configured cost rates are synthetic
evidence, not measurements of real model quality, provider billing, or market
prices. The demo's reviewer action is simulated, not a real human assessment.

Publication of this GitHub Release does not upload anything to PyPI, deploy
the application, or authorize a model deployment.
