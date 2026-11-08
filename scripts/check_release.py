"""Check release candidates locally without publishing or touching runtime data."""

import argparse
import os
import secrets
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import Settings, get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "credentials",
}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".pyc", ".pyo", ".pem", ".key"}


class ReleaseCheckError(Exception):
    """Raised when a candidate distribution fails a release invariant."""


def project_version() -> str:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as source:
        version = tomllib.load(source)["project"]["version"]
    if version != Settings.model_fields["app_version"].default:
        raise ReleaseCheckError("Package version and default API version differ.")
    return version


@contextmanager
def isolated_settings(database_url: str) -> Iterator[None]:
    """Temporarily replace task settings and restore every original value."""

    overrides = {
        "MODELSENTRY_DATABASE_URL": database_url,
        "MODELSENTRY_ENVIRONMENT": "testing",
        "MODELSENTRY_API_KEY_PEPPER": secrets.token_urlsafe(32),
        "MODELSENTRY_BOOTSTRAP_TOKEN": secrets.token_urlsafe(32),
    }
    previous = {key: os.environ.get(key) for key in overrides}
    try:
        os.environ.update(overrides)
        get_settings.cache_clear()
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def verify_migrations() -> None:
    """Exercise the complete migration chain using only a disposable database."""

    with tempfile.TemporaryDirectory(prefix="modelsentry-migrations-") as directory:
        database_url = "sqlite+pysqlite:///" + (Path(directory) / "check.db").as_posix()
        with isolated_settings(database_url):
            config = Config(str(PROJECT_ROOT / "alembic.ini"))
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "base")
            engine = create_engine(database_url)
            try:
                if set(inspect(engine).get_table_names()) - {"alembic_version"}:
                    raise ReleaseCheckError("Downgrade left application tables behind.")
            finally:
                engine.dispose()
    print("MIGRATIONS_PASSED")


def _safe_members(names: list[str]) -> None:
    for name in names:
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or FORBIDDEN_PARTS.intersection(path.parts)
            or path.suffix.lower() in FORBIDDEN_SUFFIXES
            or (path.name.startswith(".env") and path.name != ".env.example")
        ):
            raise ReleaseCheckError(f"Unexpected local, secret, or unsafe file: {name}")


def _one_file(directory: Path, pattern: str) -> Path:
    matches = list(directory.glob(pattern))
    if len(matches) != 1:
        raise ReleaseCheckError(f"Expected exactly one {pattern} in {directory}.")
    return matches[0]


def verify_artifacts(directory: Path) -> None:
    """Check distributions without extracting or executing archive members."""

    version = project_version()
    wheel = _one_file(directory, "*.whl")
    source_distribution = _one_file(directory, "*.tar.gz")
    if wheel.name != f"modelsentry-{version}-py3-none-any.whl":
        raise ReleaseCheckError("Wheel filename does not match the project version.")
    if source_distribution.name != f"modelsentry-{version}.tar.gz":
        raise ReleaseCheckError("Source archive does not match the project version.")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        _safe_members(names)
        required = {"app/main.py", "app/auth/security.py", "app/core/config.py"}
        if not required.issubset(names):
            raise ReleaseCheckError("The wheel is missing application modules.")
        metadata_path = f"modelsentry-{version}.dist-info/METADATA"
        if metadata_path not in names:
            raise ReleaseCheckError("The wheel is missing package metadata.")
        metadata = BytesParser(policy=policy.default).parsebytes(
            archive.read(metadata_path), headersonly=True
        )
        if metadata.get_all("Version") != [version]:
            raise ReleaseCheckError("Wheel metadata has an unexpected version.")
        if metadata.get_all("License-Expression") != ["MIT"]:
            raise ReleaseCheckError("Wheel metadata must declare the MIT license.")
        if metadata.get_all("License-File") != ["LICENSE"]:
            raise ReleaseCheckError("Wheel metadata must reference LICENSE.")
        license_path = f"modelsentry-{version}.dist-info/licenses/LICENSE"
        if license_path not in names:
            raise ReleaseCheckError("The wheel is missing its license file.")
        if archive.read(license_path) != (PROJECT_ROOT / "LICENSE").read_bytes():
            raise ReleaseCheckError("The wheel license differs from LICENSE.")
    with tarfile.open(source_distribution, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        _safe_members(names)
        if any(member.issym() or member.islnk() for member in members):
            raise ReleaseCheckError("Source distribution must not contain links.")
        prefix = f"modelsentry-{version}/"
        required = {
            "alembic.ini",
            "README.md",
            "LICENSE",
            "SECURITY.md",
            "MANIFEST.in",
            "pyproject.toml",
            "migrations/env.py",
            "migrations/script.py.mako",
            "migrations/versions/0010_harden_authentication_audit.py",
            "scripts/check_release.py",
            "docs/RELEASE_CHECKLIST.md",
        }
        if not {prefix + path for path in required}.issubset(names):
            raise ReleaseCheckError("The source distribution is missing release files.")
        license_file = archive.extractfile(prefix + "LICENSE")
        if license_file is None:
            raise ReleaseCheckError("The source distribution license is not a file.")
        with license_file:
            if license_file.read() != (PROJECT_ROOT / "LICENSE").read_bytes():
                raise ReleaseCheckError("The source distribution license differs.")
    print("ARTIFACTS_PASSED")


def smoke_test_wheel(directory: Path) -> None:
    """Prove the built wheel imports from an isolated environment, not source."""

    wheel = _one_file(directory, "*.whl").resolve()
    with tempfile.TemporaryDirectory(prefix="modelsentry-wheel-") as directory_name:
        directory_path = Path(directory_name)
        environment = directory_path / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        executable = environment / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        subprocess.run(
            [
                str(executable),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                str(wheel),
            ],
            check=True,
            cwd=directory_path,
        )
        clean_environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("MODELSENTRY_") and key != "PYTHONPATH"
        }
        clean_environment["MODELSENTRY_ENVIRONMENT"] = "testing"
        code = """
from pathlib import Path
import asyncio
import sys
import app
from app.main import create_app

assert Path(app.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
application = create_app()

async def assert_status(path, expected):
    messages = []
    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}
    async def send(message):
        messages.append(message)
    scope = {
        'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
        'method': 'GET', 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
        'query_string': b'', 'root_path': '', 'headers': [],
        'server': ('127.0.0.1', 8000), 'client': ('127.0.0.1', 1),
    }
    await application(scope, receive, send)
    status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
    assert status == expected, (path, status, expected)

async def main():
    await assert_status('/api/v1/health', 200)
    await assert_status('/api/v1/models', 401)

asyncio.run(main())
print('WHEEL_SMOKE_PASSED')
"""
        subprocess.run(
            [str(executable), "-c", code],
            check=True,
            cwd=directory_path,
            env=clean_environment,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=["migrations", "artifacts", "smoke"])
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args()
    try:
        if args.check == "migrations":
            verify_migrations()
        elif args.check == "artifacts":
            verify_artifacts(args.directory)
        else:
            smoke_test_wheel(args.directory)
    except (ReleaseCheckError, subprocess.CalledProcessError) as error:
        print(f"RELEASE_CHECK_FAILED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
