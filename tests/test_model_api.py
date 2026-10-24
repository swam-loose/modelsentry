from fastapi.testclient import TestClient


def make_payload(
    *,
    slug: str = "mock-evaluator",
    model_identifier: str = "deterministic-v1",
) -> dict[str, str]:
    return {
        "name": "Mock Evaluator",
        "slug": slug,
        "provider": "mock",
        "model_identifier": model_identifier,
        "description": "Deterministic model used for local evaluation tests.",
    }


def test_create_and_get_registered_model(client: TestClient) -> None:
    create_response = client.post("/api/v1/models", json=make_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["slug"] == "mock-evaluator"
    assert created["provider"] == "mock"
    assert created["is_active"] is True

    get_response = client.get(f"/api/v1/models/{created['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == created


def test_list_registered_models(client: TestClient) -> None:
    client.post("/api/v1/models", json=make_payload())
    client.post(
        "/api/v1/models",
        json=make_payload(
            slug="second-mock",
            model_identifier="deterministic-v2",
        ),
    )

    response = client.get("/api/v1/models")

    assert response.status_code == 200
    assert [model["slug"] for model in response.json()] == [
        "mock-evaluator",
        "second-mock",
    ]


def test_reject_duplicate_slug(client: TestClient) -> None:
    client.post("/api/v1/models", json=make_payload())

    response = client.post(
        "/api/v1/models",
        json=make_payload(model_identifier="another-identifier"),
    )

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


def test_return_not_found_for_unknown_model(client: TestClient) -> None:
    response = client.get("/api/v1/models/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
