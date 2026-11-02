from fastapi.testclient import TestClient


def create_comparison_dependencies(client: TestClient) -> dict[str, str]:
    baseline_model = client.post(
        "/api/v1/models",
        json={
            "name": "Baseline Model",
            "slug": "baseline-model",
            "provider": "mock",
            "model_identifier": "baseline-v1",
            "input_cost_per_million": "0.50",
            "output_cost_per_million": "1.50",
        },
    ).json()
    candidate_model = client.post(
        "/api/v1/models",
        json={
            "name": "Candidate Model",
            "slug": "candidate-model",
            "provider": "mock",
            "model_identifier": "candidate-v1",
            "input_cost_per_million": "0.60",
            "output_cost_per_million": "1.60",
        },
    ).json()
    prompt = client.post(
        "/api/v1/prompts",
        json={
            "name": "Comparison Prompt",
            "slug": "comparison-prompt",
            "initial_version": {
                "user_prompt_template": "Answer: {{question}}",
                "variables": ["question"],
            },
        },
    ).json()
    dataset = client.post(
        "/api/v1/datasets",
        json={"name": "Comparison Cases", "slug": "comparison-cases"},
    ).json()
    version = client.post(
        f"/api/v1/datasets/{dataset['id']}/versions",
        json={
            "cases": [
                {
                    "case_key": "candidate-marker",
                    "input": {"question": "Return the model marker."},
                    "expected_output": {"contains": "candidate-v1"},
                }
            ]
        },
    ).json()
    shared = {
        "prompt_version_id": prompt["versions"][0]["id"],
        "dataset_version_id": version["id"],
    }
    baseline = client.post(
        "/api/v1/runs",
        json={"registered_model_id": baseline_model["id"], **shared},
    ).json()
    candidate = client.post(
        "/api/v1/runs",
        json={"registered_model_id": candidate_model["id"], **shared},
    ).json()
    return {"baseline_run_id": baseline["id"], "candidate_run_id": candidate["id"]}


def test_compare_completed_runs_with_quality_and_cost_evidence(
    client: TestClient,
) -> None:
    payload = create_comparison_dependencies(client)

    response = client.post("/api/v1/run-comparisons", json=payload)

    assert response.status_code == 200
    comparison = response.json()
    assert comparison["baseline"]["run_id"] == payload["baseline_run_id"]
    assert comparison["candidate"]["run_id"] == payload["candidate_run_id"]
    assert comparison["quality_outcome"] == "improved"
    assert comparison["improved_cases"] == 1
    assert comparison["regressed_cases"] == 0
    assert comparison["cases"][0]["quality_change"] == "improved"
    assert comparison["candidate"]["estimated_cost_usd"] != "0E-8"
    assert comparison["candidate"]["token_usage_estimated"] is True


def test_comparison_returns_not_found_and_rejects_same_run(
    client: TestClient,
) -> None:
    payload = create_comparison_dependencies(client)
    unknown = "00000000-0000-0000-0000-000000000000"

    missing = client.post(
        "/api/v1/run-comparisons",
        json={**payload, "candidate_run_id": unknown},
    )
    same = client.post(
        "/api/v1/run-comparisons",
        json={
            "baseline_run_id": payload["baseline_run_id"],
            "candidate_run_id": payload["baseline_run_id"],
        },
    )

    assert missing.status_code == 404
    assert same.status_code == 422


def test_comparison_requires_same_dataset_version(client: TestClient) -> None:
    payload = create_comparison_dependencies(client)
    candidate_run = client.get(f"/api/v1/runs/{payload['candidate_run_id']}").json()
    other_dataset = client.post(
        "/api/v1/datasets",
        json={"name": "Other Cases", "slug": "other-cases"},
    ).json()
    other_version = client.post(
        f"/api/v1/datasets/{other_dataset['id']}/versions",
        json={
            "cases": [
                {
                    "case_key": "other-case",
                    "input": {"question": "Other question"},
                    "expected_output": {"contains": "candidate-v1"},
                }
            ]
        },
    ).json()
    other_run = client.post(
        "/api/v1/runs",
        json={
            "registered_model_id": candidate_run["registered_model_id"],
            "prompt_version_id": candidate_run["prompt_version_id"],
            "dataset_version_id": other_version["id"],
        },
    ).json()

    response = client.post(
        "/api/v1/run-comparisons",
        json={
            "baseline_run_id": payload["baseline_run_id"],
            "candidate_run_id": other_run["id"],
        },
    )

    assert response.status_code == 409
    assert "same immutable dataset version" in response.json()["detail"]
