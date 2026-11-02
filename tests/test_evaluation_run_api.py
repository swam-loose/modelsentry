from uuid import UUID

from fastapi.testclient import TestClient


def create_dependencies(
    client: TestClient,
    *,
    provider: str = "mock",
) -> dict[str, str]:
    model = client.post(
        "/api/v1/models",
        json={
            "name": f"{provider.title()} Evaluator",
            "slug": f"{provider}-evaluator",
            "provider": provider,
            "model_identifier": "deterministic-v1",
        },
    ).json()
    prompt = client.post(
        "/api/v1/prompts",
        json={
            "name": "Geography Answer",
            "slug": "geography-answer",
            "initial_version": {
                "system_prompt": "Answer from synthetic evidence.",
                "user_prompt_template": "Question: {{question}}",
                "variables": ["question"],
            },
        },
    ).json()
    dataset = client.post(
        "/api/v1/datasets",
        json={
            "name": "Geography QA",
            "slug": "geography-qa",
        },
    ).json()
    dataset_version = client.post(
        f"/api/v1/datasets/{dataset['id']}/versions",
        json={
            "cases": [
                {
                    "case_key": "capital-france",
                    "input": {
                        "question": "What is the capital of France?",
                        "mock_response": "Paris is the capital of France.",
                    },
                    "expected_output": {"contains": "Paris"},
                },
                {
                    "case_key": "capital-brazil",
                    "input": {
                        "question": "What is the capital of Brazil?",
                        "mock_response": "Brasilia is the capital of Brazil.",
                    },
                    "expected_output": {"contains": "Brasilia"},
                },
            ]
        },
    ).json()
    return {
        "registered_model_id": model["id"],
        "prompt_version_id": prompt["versions"][0]["id"],
        "dataset_version_id": dataset_version["id"],
    }


def test_create_list_and_get_mock_evaluation_run(client: TestClient) -> None:
    payload = create_dependencies(client)

    create_response = client.post("/api/v1/runs", json=payload)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["status"] == "completed"
    assert created["total_cases"] == 2
    assert created["succeeded_cases"] == 2
    assert created["errored_cases"] == 0
    assert [result["position"] for result in created["results"]] == [0, 1]
    assert created["results"][0]["output_text"] == ("Paris is the capital of France.")

    list_response = client.get("/api/v1/runs")
    get_response = client.get(f"/api/v1/runs/{created['id']}")

    assert list_response.status_code == 200
    assert [run["id"] for run in list_response.json()] == [created["id"]]
    assert get_response.status_code == 200
    assert get_response.json() == created


def test_reject_unsupported_provider(client: TestClient) -> None:
    payload = create_dependencies(client, provider="ollama")

    response = client.post("/api/v1/runs", json=payload)

    assert response.status_code == 422
    assert "not executable" in response.json()["detail"]


def test_return_not_found_for_unknown_run_and_model(client: TestClient) -> None:
    unknown_id = "00000000-0000-0000-0000-000000000000"
    payload = {
        "registered_model_id": unknown_id,
        "prompt_version_id": str(UUID(int=1)),
        "dataset_version_id": str(UUID(int=2)),
    }

    assert client.get(f"/api/v1/runs/{unknown_id}").status_code == 404
    assert client.post("/api/v1/runs", json=payload).status_code == 404
