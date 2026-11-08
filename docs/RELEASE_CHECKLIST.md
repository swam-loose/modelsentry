# Release 0.1.0 checklist

This is a release candidate checklist, not an automatic publication workflow.
Do not create a tag, GitHub Release, PyPI upload, or deployment merely because
the validation commands pass.

## Before merging

- [ ] Apply the candidate on an isolated branch based on current `develop`.
- [ ] Run Ruff, formatting, tests, and at least 95% application coverage.
- [ ] Run `python scripts/check_release.py migrations` against its disposable
  database. It must upgrade, check for drift, and downgrade to base successfully.
- [ ] Confirm bootstrap rollback and simultaneous-bootstrap tests pass.
- [ ] Confirm a reviewer cannot decide someone else's assignment and that
  administrator overrides record the actual actor.
- [ ] Confirm CI is green on both Windows and Linux for the exact PR commit.
- [ ] Confirm the build job passes metadata, archive, and installed-wheel checks.
- [ ] Review every staged file; never include a real `.env`, raw API key,
  database, virtual environment, or personal dataset.

## Local validation in PowerShell

Run one command at a time from the checkout, using its virtual environment:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install --editable ".[dev]"
& ".\.venv\Scripts\python.exe" -m ruff check app tests migrations scripts
& ".\.venv\Scripts\python.exe" -m ruff format --check app tests migrations scripts
$testTemp = Join-Path $env:LOCALAPPDATA ("ModelSentry\pytest-" + [guid]::NewGuid().ToString("N")); & ".\.venv\Scripts\python.exe" -m pytest tests "--basetemp=$testTemp" -p "no:cacheprovider" --cov=app --cov-report=term-missing
& ".\.venv\Scripts\python.exe" scripts/check_release.py migrations
& ".\.venv\Scripts\python.exe" -m build
& ".\.venv\Scripts\python.exe" -m twine check --strict "dist/*"
& ".\.venv\Scripts\python.exe" scripts/check_release.py artifacts dist
& ".\.venv\Scripts\python.exe" scripts/check_release.py smoke dist
```

Migration verification temporarily overrides process settings and restores them
even after failure. It never downgrades your runtime database. For the runtime
database, make a backup first and run only `python -m alembic upgrade head`.
Do not run destructive migration tests against a database with real data.

The source distribution includes Alembic configuration and migration history.
The wheel contains the runtime Python package; the documented migration CLI
still requires the source checkout or unpacked source distribution.

## Maintainer approval before publication

- [x] Maintainer approved the MIT license with copyright attribution to
  Wilian Ataide. The canonical text is in `LICENSE`.
- [ ] Confirm the final source distribution and wheel contain the approved
  license and that wheel metadata declares `License-Expression: MIT`.
- [ ] Complete a local demo with synthetic data and independent random secrets.
  Follow [the synthetic demo guide](SYNTHETIC_DEMO.md), confirm the expected
  blocked/passed decisions, and review `SYNTHETIC_DEMO_PASSED`. Its reviewer
  action is simulated and is not a real release authorization.
- [ ] Confirm no production credentials or user data appear in artifacts.
- [ ] Merge approved changes into `main` and wait for its own CI run to pass.
- [ ] Confirm the version and final release notes against the exact commit.
- [ ] Explicitly authorize the release tag, release visibility, and artifacts.

CI has only `contents: read` permission, uses immutable action SHAs, and never
publishes packages, creates release tags, or deploys the application.
