import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_ci_runs_on_windows_and_linux_without_write_permissions() -> None:
    content = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    workflow = yaml.load(content, Loader=yaml.BaseLoader)

    assert set(workflow["on"]) == {"pull_request", "push", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    quality = workflow["jobs"]["quality"]
    assert quality["strategy"]["matrix"]["os"] == ["ubuntu-latest", "windows-latest"]
    assert workflow["jobs"]["build"]["needs"] == "quality"
    assert "secrets." not in content
    assert "pull_request_target" not in content


def test_ci_actions_are_pinned_and_publication_is_not_automatic() -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", step["uses"])
                if step["uses"].startswith("actions/checkout@"):
                    assert step["with"]["persist-credentials"] == "false"
            if "run" in step:
                assert "twine upload" not in step["run"]
                assert "gh release create" not in step["run"]
