from fastapi.testclient import TestClient


def create_completed_run(client: TestClient) -> dict[str, object]:
    model = client.post(
        "/api/v1/models",
        json={
            "name": "Mock Evaluator",
            "slug": "mock-evaluator",
            "provider": "mock",
            "model_identifier": "deterministic-v1",
        },
    ).json()
    prompt = client.post(
        "/api/v1/prompts",
        json={
            "name": "Geography Answer",
            "slug": "geography-answer",
            "initial_version": {
                "user_prompt_template": "Question: {{question}}",
                "variables": ["question"],
            },
        },
    ).json()
    dataset = client.post(
        "/api/v1/datasets",
        json={"name": "Geography QA", "slug": "geography-qa"},
    ).json()
    dataset_version = client.post(
        f"/api/v1/datasets/{dataset['id']}/versions",
        json={
            "cases": [
                {
                    "case_key": "capital-france",
                    "input": {
                        "question": "What is the capital of France?",
                        "mock_response": "Paris",
                    },
                    "expected_output": "Paris",
                }
            ]
        },
    ).json()
    response = client.post(
        "/api/v1/runs",
        json={
            "registered_model_id": model["id"],
            "prompt_version_id": prompt["versions"][0]["id"],
            "dataset_version_id": dataset_version["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_request_and_approve_human_review(client: TestClient) -> None:
    run = create_completed_run(client)

    create_response = client.post(
        "/api/v1/reviews",
        json={
            "run_id": run["id"],
            "reviewer": " QA.Lead@Example.com ",
            "reviewer_role": "release-manager",
        },
    )

    assert create_response.status_code == 201
    review = create_response.json()
    assert review["status"] == "pending"
    assert review["reviewer"] == "qa.lead@example.com"

    pending_run = client.get(f"/api/v1/runs/{run['id']}").json()
    assert pending_run["approval_status"] == "pending"
    assert [item["id"] for item in pending_run["reviews"]] == [review["id"]]

    decision_response = client.patch(
        f"/api/v1/reviews/{review['id']}",
        json={
            "decision": "approved",
            "rationale": "All deterministic evidence was reviewed.",
        },
    )

    assert decision_response.status_code == 200
    assert decision_response.json()["status"] == "approved"
    assert decision_response.json()["decided_at"] is not None
    approved_run = client.get(f"/api/v1/runs/{run['id']}").json()
    assert approved_run["approval_status"] == "approved"


def test_rejection_requires_rationale(client: TestClient) -> None:
    run = create_completed_run(client)
    review = client.post(
        "/api/v1/reviews",
        json={"run_id": run["id"], "reviewer": "qa.lead@example.com"},
    ).json()

    missing_rationale = client.patch(
        f"/api/v1/reviews/{review['id']}",
        json={"decision": "rejected"},
    )
    rejected = client.patch(
        f"/api/v1/reviews/{review['id']}",
        json={"decision": "rejected", "rationale": "Evidence is insufficient."},
    )

    assert missing_rationale.status_code == 422
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert (
        client.get(f"/api/v1/runs/{run['id']}").json()["approval_status"] == "rejected"
    )


def test_duplicate_assignment_and_decision_rewrite_conflict(
    client: TestClient,
) -> None:
    run = create_completed_run(client)
    payload = {"run_id": run["id"], "reviewer": "qa.lead@example.com"}
    review = client.post("/api/v1/reviews", json=payload).json()

    duplicate = client.post("/api/v1/reviews", json=payload)
    first_decision = client.patch(
        f"/api/v1/reviews/{review['id']}",
        json={"decision": "approved"},
    )
    rewritten = client.patch(
        f"/api/v1/reviews/{review['id']}",
        json={"decision": "rejected", "rationale": "Changed my mind."},
    )

    assert duplicate.status_code == 409
    assert first_decision.status_code == 200
    assert rewritten.status_code == 409


def test_list_filters_and_missing_review(client: TestClient) -> None:
    run = create_completed_run(client)
    created = client.post(
        "/api/v1/reviews",
        json={"run_id": run["id"], "reviewer": "qa.lead@example.com"},
    ).json()

    queue_response = client.get(
        "/api/v1/reviews",
        params={"status": "pending", "reviewer": "QA.LEAD@EXAMPLE.COM"},
    )
    empty_response = client.get(
        "/api/v1/reviews",
        params={"status": "approved"},
    )
    missing_response = client.get(
        "/api/v1/reviews/00000000-0000-0000-0000-000000000000"
    )

    assert queue_response.status_code == 200
    assert [review["id"] for review in queue_response.json()] == [created["id"]]
    assert empty_response.json() == []
    assert missing_response.status_code == 404
