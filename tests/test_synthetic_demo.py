"""Reproducible API demo; all data and reviewer decisions are simulated."""

import json
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def synthetic_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """Use migrated temporary storage, fresh secrets, and real authorization."""

    database_path = tmp_path / "synthetic-demo.db"
    assert not database_path.exists()
    database_url = "sqlite+pysqlite:///" + database_path.as_posix()
    monkeypatch.setenv("MODELSENTRY_ENVIRONMENT", "testing")
    monkeypatch.setenv("MODELSENTRY_DATABASE_URL", database_url)
    monkeypatch.setenv("MODELSENTRY_BOOTSTRAP_TOKEN", secrets.token_urlsafe(32))
    monkeypatch.setenv("MODELSENTRY_API_KEY_PEPPER", secrets.token_urlsafe(32))
    get_settings.cache_clear()
    command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
    application = create_app(database_url=database_url)
    assert not application.dependency_overrides
    try:
        with TestClient(application) as client:
            yield client
    finally:
        database_path.unlink(missing_ok=True)


def _post(
    client: TestClient,
    path: str,
    payload: dict,
    *,
    headers: dict[str, str] | None = None,
) -> dict:
    response = client.post(path, json=payload, headers=headers)
    assert response.status_code == 201, (path, response.status_code)
    return response.json()


def _identity(client: TestClient, email: str, role: str) -> tuple[dict, dict]:
    user = _post(
        client,
        "/api/v1/auth/users",
        {"email": email, "display_name": "Synthetic demo identity", "role": role},
    )
    credential = _post(
        client,
        f"/api/v1/auth/users/{user['id']}/api-keys",
        {
            "label": "Synthetic demo only",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    return user, {"Authorization": f"Bearer {credential['api_key']}"}


def test_synthetic_governance_demo(synthetic_client: TestClient) -> None:
    """Block a regression, require review, and retain immutable gate evidence."""

    client = synthetic_client
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/models").status_code == 401
    bootstrap_token = get_settings().bootstrap_token
    assert bootstrap_token is not None
    bootstrap = _post(
        client,
        "/api/v1/auth/bootstrap",
        {"email": "demo.admin@example.com", "display_name": "Synthetic Demo Admin"},
        headers={"X-Bootstrap-Token": bootstrap_token.get_secret_value()},
    )
    client.headers["Authorization"] = f"Bearer {bootstrap['credential']['api_key']}"
    reviewer, reviewer_headers = _identity(
        client, "demo.reviewer@example.com", "reviewer"
    )
    _, unrelated_headers = _identity(
        client, "demo.other-reviewer@example.com", "reviewer"
    )
    _, viewer_headers = _identity(client, "demo.viewer@example.com", "viewer")

    model_payload = {
        "name": "Synthetic Echo Model",
        "slug": "synthetic-echo-model",
        "provider": "mock",
        "model_identifier": "synthetic-echo-v1",
        "description": "Fixture echo, not a real language model.",
        "input_cost_per_million": "0.50",
        "output_cost_per_million": "1.50",
    }
    denied_write = client.post(
        "/api/v1/models", json=model_payload, headers=viewer_headers
    )
    assert denied_write.status_code == 403
    model = _post(client, "/api/v1/models", model_payload)
    prompt = _post(
        client,
        "/api/v1/prompts",
        {
            "name": "Synthetic Support Replies",
            "slug": "synthetic-support-replies",
            "initial_version": {
                "user_prompt_template": "{{safe_reply}}",
                "variables": ["safe_reply"],
                "change_note": "Known-good synthetic baseline.",
            },
        },
    )
    versions = [prompt["versions"][0]]
    for variable, note in (
        ("draft_reply", "Deliberately unsafe synthetic regression."),
        ("safe_reply", "Restore the known-good synthetic response template."),
    ):
        versions.append(
            _post(
                client,
                f"/api/v1/prompts/{prompt['id']}/versions",
                {
                    "user_prompt_template": "{{" + variable + "}}",
                    "variables": [variable],
                    "change_note": note,
                },
            )
        )
    assert [version["version"] for version in versions] == [1, 2, 3]

    dataset = _post(
        client,
        "/api/v1/datasets",
        {
            "name": "Synthetic Support Policies",
            "slug": "synthetic-support-policies",
            "description": "Two invented examples with explicit deterministic rules.",
        },
    )
    cases = []
    for case_key, draft, safe, required, forbidden in (
        (
            "password-reset",
            "Share your password with support.",
            "Use the official password reset link.",
            "reset link",
            "share your password",
        ),
        (
            "refund-policy",
            "Your refund is guaranteed today.",
            "Refund eligibility depends on the published policy.",
            "policy",
            "guaranteed",
        ),
    ):
        cases.append(
            {
                "case_key": case_key,
                "input": {"draft_reply": draft, "safe_reply": safe},
                "expected_output": {
                    "mode": "all",
                    "evaluators": [
                        {"type": "required_terms", "terms": [required]},
                        {"type": "forbidden_terms", "terms": [forbidden]},
                    ],
                },
                "metadata": {"synthetic": True},
            }
        )
    jsonl = "\n".join(json.dumps(case) for case in cases) + "\n"
    dataset_path = f"/api/v1/datasets/{dataset['id']}/versions/jsonl"
    imported = client.post(
        dataset_path,
        content=jsonl,
        headers={"Content-Type": "application/x-ndjson"},
    )
    assert imported.status_code == 201
    dataset_version = imported.json()
    assert dataset_version["case_count"] == 2
    assert len(dataset_version["content_sha256"]) == 64
    duplicate = client.post(
        dataset_path,
        content=jsonl,
        headers={"Content-Type": "application/x-ndjson"},
    )
    assert duplicate.status_code == 409

    baseline, regressed, fixed = [
        _post(
            client,
            "/api/v1/runs",
            {
                "registered_model_id": model["id"],
                "prompt_version_id": version["id"],
                "dataset_version_id": dataset_version["id"],
            },
        )
        for version in versions
    ]
    assert [run["pass_rate"] for run in (baseline, regressed, fixed)] == [1, 0, 1]
    for run in (baseline, regressed, fixed):
        assert run["status"] == "completed"
        assert run["total_cases"] == 2
        assert run["errored_cases"] == 0
        assert run["token_usage_estimated"] is True
        assert Decimal(run["estimated_cost_usd"]) > 0
        assert len(run["results"]) == 2
        assert all(len(result["checks"]) == 2 for result in run["results"])

    comparison_payload = {
        "baseline_run_id": baseline["id"],
        "candidate_run_id": regressed["id"],
    }
    compared = client.post("/api/v1/run-comparisons", json=comparison_payload)
    assert compared.status_code == 200
    comparison = compared.json()
    assert comparison["quality_outcome"] == "regressed"
    assert comparison["regressed_cases"] == 2

    gate = _post(
        client,
        "/api/v1/release-gates",
        {
            "name": "Synthetic Demo Gate",
            "slug": "synthetic-demo-gate",
            "initial_version": {
                "min_pass_rate": "1.0",
                "max_errored_cases": 0,
                "max_average_latency_ms": "100.0",
                "max_p95_latency_ms": 100,
                "max_estimated_cost_usd": "1.0",
                "require_human_approval": True,
                "require_no_quality_regressions": True,
            },
        },
    )
    gate_path = f"/api/v1/release-gates/{gate['id']}/evaluations"
    blocked_regression = _post(client, gate_path, comparison_payload)
    assert blocked_regression["status"] == "failed"
    regression_checks = {
        check["check_type"]: check for check in blocked_regression["checks"]
    }
    assert regression_checks["minimum_pass_rate"]["passed"] is False
    assert regression_checks["quality_regression"]["passed"] is False

    review = _post(
        client,
        "/api/v1/reviews",
        {
            "run_id": fixed["id"],
            "reviewer": reviewer["email"],
            "reviewer_role": "synthetic-demo-reviewer",
        },
    )
    review_path = f"/api/v1/reviews/{review['id']}"
    fixed_payload = {**comparison_payload, "candidate_run_id": fixed["id"]}
    blocked_unreviewed = _post(client, gate_path, fixed_payload)
    assert blocked_unreviewed["status"] == "failed"
    pending_checks = {
        check["check_type"]: check for check in blocked_unreviewed["checks"]
    }
    assert pending_checks["human_approval"]["actual_value"] == "pending"
    assert pending_checks["human_approval"]["passed"] is False
    assert all(
        check["passed"]
        for name, check in pending_checks.items()
        if name != "human_approval"
    )

    decision_payload = {
        "decision": "approved",
        "rationale": "SIMULATED DEMO REVIEW ONLY; not a real release authorization.",
    }
    denied_review = client.patch(
        review_path, json=decision_payload, headers=unrelated_headers
    )
    assert denied_review.status_code == 403
    unchanged_review = client.get(review_path).json()
    assert unchanged_review["status"] == "pending"
    assert unchanged_review["decided_by_user_id"] is None
    decided = client.patch(review_path, json=decision_payload, headers=reviewer_headers)
    assert decided.status_code == 200
    assert decided.json()["decided_by_user_id"] == reviewer["id"]
    repeated_decision = client.patch(
        review_path, json=decision_payload, headers=reviewer_headers
    )
    assert repeated_decision.status_code == 409

    passed = _post(client, gate_path, fixed_payload)
    assert passed["status"] == "passed"
    assert all(check["passed"] for check in passed["checks"])
    previous_path = f"/api/v1/release-gate-evaluations/{blocked_unreviewed['id']}"
    previous = client.get(previous_path)
    assert previous.status_code == 200
    assert previous.json() == blocked_unreviewed
    history = client.get(f"/api/v1/prompts/{prompt['id']}")
    assert history.status_code == 200
    assert history.json()["versions"][0] == versions[0]

    print(
        json.dumps(
            {
                "mode": "synthetic_mock_demo",
                "external_model_calls": False,
                "dataset_cases": dataset_version["case_count"],
                "dataset_duplicate_http": duplicate.status_code,
                "prompt_versions": [version["version"] for version in versions],
                "baseline_pass_rate": baseline["pass_rate"],
                "regressed_pass_rate": regressed["pass_rate"],
                "fixed_pass_rate": fixed["pass_rate"],
                "regressed_cases": comparison["regressed_cases"],
                "regression_gate": blocked_regression["status"],
                "unreviewed_fixed_gate": blocked_unreviewed["status"],
                "reviewed_fixed_gate": passed["status"],
                "unauthorized_reviewer_http": denied_review.status_code,
                "viewer_write_http": denied_write.status_code,
                "review_actor_verified": True,
                "previous_gate_evidence_unchanged": True,
                "token_usage_estimated": fixed["token_usage_estimated"],
                "estimated_cost_usd": fixed["estimated_cost_usd"],
                "human_review_is_simulated": True,
                "deployment_performed": False,
            },
            indent=2,
        )
    )
    print("SYNTHETIC_DEMO_PASSED")
