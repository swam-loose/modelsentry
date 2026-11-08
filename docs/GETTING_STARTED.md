# Getting started

[README](../README.md) · [API guide](API_GUIDE.md) · [Synthetic demo](SYNTHETIC_DEMO.md)

This guide starts a persistent **local** ModelSentry API from source. The
isolated demo in the README is a separate workflow: it configures its own test
secrets and temporary database and does not need the setup below.

## Prerequisites

- Python **3.12**; the project currently requires `>=3.12,<3.13`.
- Git and a source checkout, or the unpacked source distribution.
- No Docker, WSL, Redis, PostgreSQL, GPU, or paid API account.

Use the project's interpreter explicitly. You do not need to activate the
virtual environment, run as administrator, or alter PowerShell execution policy.
Commands below assume the repository root and a fresh installation. For an
existing database, make a backup before applying migrations; do not replace its
pepper or run a downgrade as an installation step.

## Install dependencies

<details open>
<summary><strong>Windows · PowerShell</strong></summary>

```powershell
py -3.12 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install --editable ".[dev]"
```

</details>

<details>
<summary><strong>Linux · Bash</strong></summary>

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --editable '.[dev]'
```

</details>

The development extra supplies pytest and the tools used by the synthetic demo
and quality checks. Source installation also provides the Alembic configuration
and migration history, which are not included in the runtime-only wheel.

## Local secrets

For a new local installation, the following command creates `.env` with two
independently generated secrets **without printing them**. It leaves an
existing `.env` unchanged and uses exclusive file creation to prevent overwrite.
Run the command from the project root.

<details open>
<summary><strong>Windows · PowerShell</strong></summary>

```powershell
& ".\.venv\Scripts\python.exe" -c "from pathlib import Path; from secrets import token_urlsafe; p=Path('.env'); p.exists() or p.open('x', encoding='utf-8').write('MODELSENTRY_ENVIRONMENT=development\nMODELSENTRY_DATABASE_URL=sqlite+pysqlite:///./modelsentry.db\nMODELSENTRY_API_KEY_PEPPER='+token_urlsafe(32)+'\nMODELSENTRY_BOOTSTRAP_TOKEN='+token_urlsafe(32)+'\n')"
```

</details>

<details>
<summary><strong>Linux · Bash</strong></summary>

```bash
.venv/bin/python -c "from pathlib import Path; from secrets import token_urlsafe; p=Path('.env'); p.exists() or p.open('x', encoding='utf-8').write('MODELSENTRY_ENVIRONMENT=development\nMODELSENTRY_DATABASE_URL=sqlite+pysqlite:///./modelsentry.db\nMODELSENTRY_API_KEY_PEPPER='+token_urlsafe(32)+'\nMODELSENTRY_BOOTSTRAP_TOKEN='+token_urlsafe(32)+'\n')"
```

</details>

If you already copied `.env.example`, replace both placeholder secrets before
starting the API. The generator above deliberately does not edit an existing
file, even when that file still contains placeholders.

| Setting | Purpose | Operational rule |
| --- | --- | --- |
| `MODELSENTRY_ENVIRONMENT` | Configuration environment | Use `development` for this local walkthrough |
| `MODELSENTRY_DATABASE_URL` | SQLAlchemy connection URL | Default local SQLite; keep backups of persistent data |
| `MODELSENTRY_API_KEY_PEPPER` | Protects persisted API-key digests | Keep stable; changing it invalidates issued keys |
| `MODELSENTRY_BOOTSTRAP_TOKEN` | Authorizes the first admin creation | Independent secret; remove after successful bootstrap |

Do not commit `.env`, paste its contents into issues, or show it in screenshots.
Production configuration rejects empty, weak, reused, or documented placeholder
secrets; selecting `production` does not supply TLS or a hardened deployment.
See [SECURITY.md](../SECURITY.md) for the actual security boundary.

## Apply migrations

Apply migrations **after** configuring `.env`:

```powershell
& ".\.venv\Scripts\python.exe" -m alembic upgrade head
```

On Linux:

```bash
.venv/bin/python -m alembic upgrade head
```

This creates or upgrades the configured database. Application startup does not
create tables automatically. Do not use `alembic downgrade` to fix an existing
installation without first understanding its data-loss implications.

## Start the server

In PowerShell:

```powershell
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

On Linux:

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Keep this terminal open. Stop the server with **Ctrl+C**. `--reload` is for
local development, not a production deployment.

| Address | Expected behavior |
| --- | --- |
| `http://127.0.0.1:8000/api/v1/health` | HTTP 200, without an API key |
| `http://127.0.0.1:8000/docs` | Interactive Swagger UI |
| `http://127.0.0.1:8000/redoc` | Read-only API documentation |
| `http://127.0.0.1:8000/api/v1/models` | HTTP 401 until a valid bearer key is supplied |

Keep the server on loopback. There is no public hosted application URL.

## Bootstrap and first requests

Continue with [Authentication in the API guide](API_GUIDE.md#authentication).
You will create the first administrator, store its one-time key, and use the
Swagger authorization control. A bootstrap token is not a normal bearer API
key, and values read from `.env` are not automatically PowerShell variables.

After successful bootstrap, remove the `MODELSENTRY_BOOTSTRAP_TOKEN` setting
from `.env` and restart the server. Remove the line rather than leaving an
empty value. Keep `MODELSENTRY_API_KEY_PEPPER` unchanged.

## Verification

From the repository root, using the existing environment:

```powershell
& ".\.venv\Scripts\python.exe" -m ruff check app tests migrations scripts
& ".\.venv\Scripts\python.exe" -m ruff format --check app tests migrations scripts
& ".\.venv\Scripts\python.exe" -m pytest tests -p "no:cacheprovider" --cov=app --cov-report=term-missing
& ".\.venv\Scripts\python.exe" scripts/check_release.py migrations
```

The last command uses its own disposable database for upgrade, drift checking,
and downgrade. It does not downgrade your normal runtime database. The
synthetic demo likewise uses temporary storage and fresh secrets.

For Linux, replace `& ".\.venv\Scripts\python.exe"` with `.venv/bin/python`.
For packaging checks and the release process, see the
[release checklist](RELEASE_CHECKLIST.md).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `.venv` interpreter not found | Run from the repository root and verify environment creation succeeded |
| Wrong Python version or missing dependencies | Use the explicit project interpreter, not global `python` |
| Placeholder / empty secret validation error | Replace the existing `.env` placeholders; the generator does not overwrite them |
| Missing database table | Check the configured URL and run `alembic upgrade head` against the intended database |
| HTTP 401 on a product route | Supply an issued bearer key, not the bootstrap token; check expiry and revocation |
| HTTP 403 | The role or review assignment does not permit the action |
| HTTP 409 on bootstrap | An initial user already exists; do not delete the database to re-bootstrap |
| Old keys stopped working after configuration changes | Check whether the pepper changed; do not keep regenerating secrets |
| Pytest cache permission warning | Keep `-p "no:cacheprovider"`; use a writable temporary directory if needed |
| Port 8000 already in use | Stop the earlier local server or choose another port and update your client URL |

Use a fresh synthetic reproduction when asking for help. Never attach a real
database, `.env`, bearer key, bootstrap token, or sensitive dataset.
