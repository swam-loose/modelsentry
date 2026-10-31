import json

from fastapi.testclient import TestClient


def make_dataset_payload() -> dict[str, str]:
    return {
        "name": "Geography QA",
        "slug": "geography-qa",
        "description": "Synthetic geography questions.",
    }


def make_case(case_key: str, question: str, answer: str) -> dict[str, object]:
    return {
        "case_key": case_key,
        "input": {"question": question},
        "expected_output": {"contains": answer},
        "metadata": {"category": "geography"},
    }


def create_dataset(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/datasets", json=make_dataset_payload())
    assert response.status_code == 201
    return response.json()


def test_create_list_and_get_evaluation_dataset(client: TestClient) -> None:
    created = create_dataset(client)

    list_response = client.get("/api/v1/datasets")
    get_response = client.get(f"/api/v1/datasets/{created['id']}")

    assert list_response.status_code == 200
    assert [dataset["slug"] for dataset in list_response.json()] == ["geography-qa"]
    assert get_response.status_code == 200
    assert get_response.json()["versions"] == []


def test_create_and_retrieve_structured_dataset_version(
    client: TestClient,
) -> None:
    dataset = create_dataset(client)
    payload = {
        "cases": [
            make_case(
                "capital-france",
                "What is the capital of France?",
                "Paris",
            ),
            make_case(
                "capital-brazil",
                "What is the capital of Brazil?",
                "Brasilia",
            ),
        ],
        "change_note": "Initial synthetic cases.",
    }

    create_response = client.post(
        f"/api/v1/datasets/{dataset['id']}/versions",
        json=payload,
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["version"] == 1
    assert created["case_count"] == 2
    assert [case["position"] for case in created["cases"]] == [0, 1]

    list_response = client.get(f"/api/v1/datasets/{dataset['id']}/versions")
    get_response = client.get(f"/api/v1/datasets/{dataset['id']}/versions/1")

    assert [version["version"] for version in list_response.json()] == [1]
    assert get_response.status_code == 200
    assert get_response.json() == created


def test_import_jsonl_dataset_version(client: TestClient) -> None:
    dataset = create_dataset(client)
    jsonl = "\n".join(
        [
            json.dumps(
                make_case(
                    "capital-france",
                    "What is the capital of France?",
                    "Paris",
                )
            ),
            json.dumps(
                make_case(
                    "capital-brazil",
                    "What is the capital of Brazil?",
                    "Brasilia",
                )
            ),
        ]
    )

    response = client.post(
        f"/api/v1/datasets/{dataset['id']}/versions/jsonl",
        params={"change_note": "Imported from JSONL."},
        content=jsonl.encode(),
        headers={"content-type": "application/x-ndjson"},
    )

    assert response.status_code == 201
    assert response.json()["case_count"] == 2
    assert response.json()["change_note"] == "Imported from JSONL."


def test_reject_invalid_and_duplicate_jsonl(client: TestClient) -> None:
    dataset = create_dataset(client)
    endpoint = f"/api/v1/datasets/{dataset['id']}/versions/jsonl"
    valid_jsonl = json.dumps(
        make_case(
            "capital-france",
            "What is the capital of France?",
            "Paris",
        )
    )

    invalid_response = client.post(
        endpoint,
        content=b"not-json",
        headers={"content-type": "application/x-ndjson"},
    )
    first_response = client.post(
        endpoint,
        content=valid_jsonl.encode(),
        headers={"content-type": "application/x-ndjson"},
    )
    duplicate_response = client.post(
        endpoint,
        content=valid_jsonl.encode(),
        headers={"content-type": "application/x-ndjson"},
    )

    assert invalid_response.status_code == 422
    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409


def test_return_not_found_for_unknown_dataset(client: TestClient) -> None:
    dataset_id = "00000000-0000-0000-0000-000000000000"

    assert client.get(f"/api/v1/datasets/{dataset_id}").status_code == 404
    assert client.get(f"/api/v1/datasets/{dataset_id}/versions").status_code == 404
