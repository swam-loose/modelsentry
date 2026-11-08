from fastapi.testclient import TestClient

from tests.test_run_comparison_api import create_comparison_dependencies


def create_gate(client: TestClient, *, require_approval: bool = True) -> dict:
    response = client.post(
        "/api/v1/release-gates",
        json={
            "name": "Production Quality Gate",
            "slug": "production-quality-gate",
            "description": "Conservative evidence requirements for release review.",
            "initial_version": {
                "min_pass_rate": "1.0",
                "max_errored_cases": 0,
                "max_average_latency_ms": "100.0",
                "max_p95_latency_ms": 100,
                "max_estimated_cost_usd": "1.0",
                "require_human_approval": require_approval,
                "require_no_quality_regressions": True,
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def approve_run(client: TestClient, run_id: str) -> None:
    review = client.post(
        "/api/v1/reviews",
        json={
            "run_id": run_id,
            "reviewer": "release.manager@example.com",
            "reviewer_role": "release-manager",
        },
    ).json()
    response = client.patch(
        f"/api/v1/reviews/{review['id']}",
        json={
            "decision": "approved",
            "rationale": "All deterministic evidence was independently reviewed.",
        },
    )
    assert response.status_code == 200


def test_create_list_get_and_version_release_gate(client: TestClient) -> None:
    gate = create_gate(client)

    version_response = client.post(
        f"/api/v1/release-gates/{gate['id']}/versions",
        json={
            "min_pass_rate": "0.95",
            "max_errored_cases": 0,
            "require_human_approval": True,
            "require_no_quality_regressions": True,
            "change_note": "Calibrated after the synthetic pilot.",
        },
    )
    list_response = client.get("/api/v1/release-gates")
    get_response = client.get(f"/api/v1/release-gates/{gate['id']}")

    assert version_response.status_code == 201
    assert version_response.json()["version"] == 2
    assert [item["id"] for item in list_response.json()] == [gate["id"]]
    assert [item["version"] for item in get_response.json()["versions"]] == [1, 2]


def test_release_gate_persists_passing_evidence(client: TestClient) -> None:
    runs = create_comparison_dependencies(client)
    approve_run(client, runs["candidate_run_id"])
    gate = create_gate(client)

    response = client.post(
        f"/api/v1/release-gates/{gate['id']}/evaluations",
        json={
            "baseline_run_id": runs["baseline_run_id"],
            "candidate_run_id": runs["candidate_run_id"],
        },
    )

    assert response.status_code == 201
    evaluation = response.json()
    assert evaluation["status"] == "passed"
    assert all(check["passed"] for check in evaluation["checks"])
    assert [check["check_type"] for check in evaluation["checks"]] == [
        "minimum_pass_rate",
        "maximum_errored_cases",
        "maximum_average_latency_ms",
        "maximum_p95_latency_ms",
        "maximum_estimated_cost_usd",
        "human_approval",
        "quality_regression",
    ]

    list_response = client.get(f"/api/v1/release-gates/{gate['id']}/evaluations")
    get_response = client.get(f"/api/v1/release-gate-evaluations/{evaluation['id']}")
    assert [item["id"] for item in list_response.json()] == [evaluation["id"]]
    assert get_response.json() == evaluation


def test_release_gate_records_failed_human_approval(client: TestClient) -> None:
    runs = create_comparison_dependencies(client)
    gate = create_gate(client)

    response = client.post(
        f"/api/v1/release-gates/{gate['id']}/evaluations",
        json={
            "baseline_run_id": runs["baseline_run_id"],
            "candidate_run_id": runs["candidate_run_id"],
        },
    )

    assert response.status_code == 201
    evaluation = response.json()
    human_check = next(
        check
        for check in evaluation["checks"]
        if check["check_type"] == "human_approval"
    )
    assert evaluation["status"] == "failed"
    assert human_check["passed"] is False
    assert human_check["actual_value"] == "not_requested"


def test_release_gate_requires_baseline_and_handles_missing_resources(
    client: TestClient,
) -> None:
    runs = create_comparison_dependencies(client)
    gate = create_gate(client, require_approval=False)
    unknown = "00000000-0000-0000-0000-000000000000"

    missing_baseline = client.post(
        f"/api/v1/release-gates/{gate['id']}/evaluations",
        json={"candidate_run_id": runs["candidate_run_id"]},
    )
    missing_gate = client.get(f"/api/v1/release-gates/{unknown}")
    missing_evaluation = client.get(f"/api/v1/release-gate-evaluations/{unknown}")

    assert missing_baseline.status_code == 409
    assert "requires a baseline" in missing_baseline.json()["detail"]
    assert missing_gate.status_code == 404
    assert missing_evaluation.status_code == 404
