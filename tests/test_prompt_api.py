from fastapi.testclient import TestClient


def make_payload() -> dict[str, object]:
    return {
        "name": "Support Answer",
        "slug": "support-answer",
        "description": "Answer support questions from supplied evidence.",
        "initial_version": {
            "system_prompt": "Answer only from supplied evidence.",
            "user_prompt_template": "Answer {{question}}.",
            "variables": ["question"],
            "change_note": "Initial version.",
        },
    }


def test_create_list_and_get_prompt(client: TestClient) -> None:
    create_response = client.post("/api/v1/prompts", json=make_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["slug"] == "support-answer"
    assert created["is_active"] is True
    assert [version["version"] for version in created["versions"]] == [1]

    list_response = client.get("/api/v1/prompts")
    get_response = client.get(f"/api/v1/prompts/{created['id']}")

    assert list_response.status_code == 200
    assert [prompt["slug"] for prompt in list_response.json()] == ["support-answer"]
    assert get_response.status_code == 200
    assert get_response.json() == created


def test_append_and_retrieve_exact_prompt_version(client: TestClient) -> None:
    prompt = client.post("/api/v1/prompts", json=make_payload()).json()

    create_response = client.post(
        f"/api/v1/prompts/{prompt['id']}/versions",
        json={
            "user_prompt_template": "Answer {{question}} concisely.",
            "variables": ["question"],
            "change_note": "Require concise answers.",
        },
    )

    assert create_response.status_code == 201
    assert create_response.json()["version"] == 2

    list_response = client.get(f"/api/v1/prompts/{prompt['id']}/versions")
    exact_response = client.get(f"/api/v1/prompts/{prompt['id']}/versions/2")

    assert [version["version"] for version in list_response.json()] == [1, 2]
    assert exact_response.status_code == 200
    assert exact_response.json() == create_response.json()


def test_reject_duplicate_prompt_slug(client: TestClient) -> None:
    client.post("/api/v1/prompts", json=make_payload())

    response = client.post("/api/v1/prompts", json=make_payload())

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


def test_return_not_found_for_unknown_prompt(client: TestClient) -> None:
    prompt_id = "00000000-0000-0000-0000-000000000000"

    assert client.get(f"/api/v1/prompts/{prompt_id}").status_code == 404
    assert client.get(f"/api/v1/prompts/{prompt_id}/versions").status_code == 404
