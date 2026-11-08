import io
import os
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

from scripts.check_release import (
    PROJECT_ROOT,
    ReleaseCheckError,
    _safe_members,
    isolated_settings,
    project_version,
    verify_artifacts,
)


def write_artifacts(
    directory: Path,
    *,
    extra_wheel_member: str | None = None,
    metadata_newline: str = "\n",
    metadata_version: str | None = None,
    license_expression: str = "MIT",
    include_wheel_license: bool = True,
    include_source_license: bool = True,
    license_contents: bytes | None = None,
) -> None:
    version = project_version()
    actual_version = version if metadata_version is None else metadata_version
    license_data = (
        (PROJECT_ROOT / "LICENSE").read_bytes()
        if license_contents is None
        else license_contents
    )
    with zipfile.ZipFile(
        directory / f"modelsentry-{version}-py3-none-any.whl", "w"
    ) as archive:
        for name in ("app/main.py", "app/auth/security.py", "app/core/config.py"):
            archive.writestr(name, "# synthetic fixture\n")
        archive.writestr(
            f"modelsentry-{version}.dist-info/METADATA",
            metadata_newline.join(
                [
                    "Metadata-Version: 2.4",
                    "Name: modelsentry",
                    f"Version: {actual_version}",
                    f"License-Expression: {license_expression}",
                    "License-File: LICENSE",
                    "",
                    "",
                ]
            ),
        )
        if include_wheel_license:
            archive.writestr(
                f"modelsentry-{version}.dist-info/licenses/LICENSE", license_data
            )
        if extra_wheel_member is not None:
            archive.writestr(extra_wheel_member, "synthetic content")
    with tarfile.open(directory / f"modelsentry-{version}.tar.gz", "w:gz") as archive:
        for name in (
            "alembic.ini",
            "README.md",
            "SECURITY.md",
            "MANIFEST.in",
            "pyproject.toml",
            "migrations/env.py",
            "migrations/script.py.mako",
            "migrations/versions/0010_harden_authentication_audit.py",
            "scripts/check_release.py",
            "docs/RELEASE_CHECKLIST.md",
        ):
            data = b"synthetic fixture"
            member = tarfile.TarInfo(f"modelsentry-{version}/{name}")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        if include_source_license:
            member = tarfile.TarInfo(f"modelsentry-{version}/LICENSE")
            member.size = len(license_data)
            archive.addfile(member, io.BytesIO(license_data))


@pytest.mark.parametrize("metadata_newline", ["\n", "\r\n"])
def test_artifact_check_accepts_complete_synthetic_distributions(
    tmp_path: Path,
    metadata_newline: str,
) -> None:
    write_artifacts(tmp_path, metadata_newline=metadata_newline)
    verify_artifacts(tmp_path)


def test_artifact_check_still_rejects_incorrect_version(tmp_path: Path) -> None:
    write_artifacts(tmp_path, metadata_newline="\r\n", metadata_version="99.0.0")
    with pytest.raises(ReleaseCheckError, match="unexpected version"):
        verify_artifacts(tmp_path)


def test_project_declares_mit_and_bundles_its_license() -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as source:
        project = tomllib.load(source)["project"]
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    license_text = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("MIT License\n")
    assert "Copyright (c) 2026 Wilian Ataide" in license_text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in license_text


def test_artifact_check_rejects_incorrect_license_metadata(tmp_path: Path) -> None:
    write_artifacts(tmp_path, license_expression="Apache-2.0")
    with pytest.raises(ReleaseCheckError, match="must declare the MIT license"):
        verify_artifacts(tmp_path)


def test_artifact_check_requires_license_inside_wheel(tmp_path: Path) -> None:
    write_artifacts(tmp_path, include_wheel_license=False)
    with pytest.raises(ReleaseCheckError, match="missing its license file"):
        verify_artifacts(tmp_path)


def test_artifact_check_requires_license_inside_source(tmp_path: Path) -> None:
    write_artifacts(tmp_path, include_source_license=False)
    with pytest.raises(ReleaseCheckError, match="missing release files"):
        verify_artifacts(tmp_path)


def test_artifact_check_rejects_replaced_license_text(tmp_path: Path) -> None:
    write_artifacts(tmp_path, license_contents=b"Not the maintainer-approved license.")
    with pytest.raises(ReleaseCheckError, match="wheel license differs"):
        verify_artifacts(tmp_path)


@pytest.mark.parametrize(
    "name",
    [
        "app/.env",
        "app/private.key",
        ".venv/bin/python",
        "app/local.db",
        "app/__pycache__/module.pyc",
        "../outside.py",
        "/absolute.py",
        "app/.env.production",
        "app\\windows-path.py",
    ],
)
def test_artifact_check_rejects_secrets_local_data_and_unsafe_paths(name: str) -> None:
    with pytest.raises(ReleaseCheckError):
        _safe_members([name])


def test_artifact_check_rejects_a_real_secret_file_in_wheel(tmp_path: Path) -> None:
    write_artifacts(tmp_path, extra_wheel_member=".env")
    with pytest.raises(ReleaseCheckError, match="secret"):
        verify_artifacts(tmp_path)


def test_artifact_check_requires_both_distributions(tmp_path: Path) -> None:
    with pytest.raises(ReleaseCheckError, match="exactly one"):
        verify_artifacts(tmp_path)


def test_release_settings_restore_runtime_environment_even_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_url = "sqlite:///do-not-touch.db"
    monkeypatch.setenv("MODELSENTRY_DATABASE_URL", original_url)
    monkeypatch.setenv("MODELSENTRY_ENVIRONMENT", "development")
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with isolated_settings("sqlite:///temporary-check.db"):
            assert os.environ["MODELSENTRY_DATABASE_URL"] != original_url
            assert os.environ["MODELSENTRY_ENVIRONMENT"] == "testing"
            raise RuntimeError("synthetic failure")

    assert os.environ["MODELSENTRY_DATABASE_URL"] == original_url
    assert os.environ["MODELSENTRY_ENVIRONMENT"] == "development"
    assert "MODELSENTRY_API_KEY_PEPPER" not in os.environ
    assert "MODELSENTRY_BOOTSTRAP_TOKEN" not in os.environ
