from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.conftest import TEST_BOOTSTRAP_TOKEN
from tests.test_human_review_api import create_completed_run


def bearer(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def create_user_and_key(
    client: TestClient,
    *,
    email: str,
    role: str,
) -> tuple[dict, str, dict]:
    user_response = client.post(
        "/api/v1/auth/users",
        json={
            "email": email,
            "display_name": f"{role.title()} User",
            "role": role,
        },
    )
    assert user_response.status_code == 201
    user = user_response.json()
    key_response = client.post(
        f"/api/v1/auth/users/{user['id']}/api-keys",
        json={"label": f"{role}-test-key"},
    )
    assert key_response.status_code == 201
    credential = key_response.json()
    return user, credential["api_key"], credential


def test_health_is_public_but_product_routes_require_authentication(
    client: TestClient,
) -> None:
    client.headers.pop("Authorization")

    health = client.get("/api/v1/health")
    missing = client.get("/api/v1/models")
    invalid = client.get(
        "/api/v1/models",
        headers=bearer("msk_invalid-credential"),
    )

    assert health.status_code == 200
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert invalid.status_code == 401


def test_bootstrap_is_one_time_and_requires_configured_token(
    client: TestClient,
) -> None:
    payload = {
        "email": "second-admin@example.com",
        "display_name": "Second Administrator",
    }

    unauthorized = client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-Bootstrap-Token": "wrong-token"},
        json=payload,
    )
    repeated = client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-Bootstrap-Token": TEST_BOOTSTRAP_TOKEN},
        json=payload,
    )

    assert unauthorized.status_code == 401
    assert repeated.status_code == 409


def test_current_identity_exposes_role_and_permissions(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "admin@example.com"
    assert payload["user"]["role"] == "admin"
    assert payload["permissions"] == ["admin", "operate", "read", "review"]
    assert payload["api_key_id"]


def test_admin_manages_users_and_one_time_api_keys(client: TestClient) -> None:
    user, raw_key, issued = create_user_and_key(
        client,
        email="viewer@example.com",
        role="viewer",
    )

    users = client.get("/api/v1/auth/users")
    keys = client.get(f"/api/v1/auth/users/{user['id']}/api-keys")
    me = client.get("/api/v1/auth/me", headers=bearer(raw_key))

    assert users.status_code == 200
    assert [item["email"] for item in users.json()] == [
        "admin@example.com",
        "viewer@example.com",
    ]
    assert keys.status_code == 200
    assert len(keys.json()) == 1
    assert "api_key" not in keys.json()[0]
    assert "key_hash" not in keys.json()[0]
    assert issued["api_key"].startswith("msk_")
    assert me.json()["user"]["role"] == "viewer"

    revoked = client.delete(f"/api/v1/auth/api-keys/{issued['id']}")
    rejected = client.get("/api/v1/auth/me", headers=bearer(raw_key))
    assert revoked.status_code == 204
    assert rejected.status_code == 401


def test_viewer_is_read_only_and_cannot_administer_identities(
    client: TestClient,
) -> None:
    _, raw_key, _ = create_user_and_key(
        client,
        email="readonly@example.com",
        role="viewer",
    )
    headers = bearer(raw_key)

    allowed = client.get("/api/v1/models", headers=headers)
    denied_write = client.post(
        "/api/v1/models",
        headers=headers,
        json={
            "name": "Denied Model",
            "slug": "denied-model",
            "provider": "mock",
            "model_identifier": "denied-v1",
        },
    )
    denied_admin = client.get("/api/v1/auth/users", headers=headers)

    assert allowed.status_code == 200
    assert denied_write.status_code == 403
    assert denied_admin.status_code == 403


def test_operator_can_operate_but_cannot_submit_review_decisions(
    client: TestClient,
) -> None:
    run = create_completed_run(client)
    review = client.post(
        "/api/v1/reviews",
        json={"run_id": run["id"], "reviewer": "reviewer@example.com"},
    ).json()
    _, raw_key, _ = create_user_and_key(
        client,
        email="operator@example.com",
        role="operator",
    )
    headers = bearer(raw_key)

    created = client.post(
        "/api/v1/models",
        headers=headers,
        json={
            "name": "Operator Model",
            "slug": "operator-model",
            "provider": "mock",
            "model_identifier": "operator-v1",
        },
    )
    denied_decision = client.patch(
        f"/api/v1/reviews/{review['id']}",
        headers=headers,
        json={"decision": "approved"},
    )

    assert created.status_code == 201
    assert denied_decision.status_code == 403


def test_reviewer_can_decide_reviews_but_cannot_operate_resources(
    client: TestClient,
) -> None:
    run = create_completed_run(client)
    review = client.post(
        "/api/v1/reviews",
        json={"run_id": run["id"], "reviewer": "reviewer@example.com"},
    ).json()
    _, raw_key, _ = create_user_and_key(
        client,
        email="reviewer@example.com",
        role="reviewer",
    )
    headers = bearer(raw_key)

    decision = client.patch(
        f"/api/v1/reviews/{review['id']}",
        headers=headers,
        json={"decision": "approved", "rationale": "Evidence verified."},
    )
    denied_operation = client.post(
        "/api/v1/models",
        headers=headers,
        json={
            "name": "Reviewer Model",
            "slug": "reviewer-model",
            "provider": "mock",
            "model_identifier": "reviewer-v1",
        },
    )

    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    assert denied_operation.status_code == 403


def test_api_key_expiration_and_missing_resources_are_reported(
    client: TestClient,
) -> None:
    user, _, _ = create_user_and_key(
        client,
        email="temporary@example.com",
        role="viewer",
    )
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    unknown = "00000000-0000-0000-0000-000000000000"

    expired = client.post(
        f"/api/v1/auth/users/{user['id']}/api-keys",
        json={"label": "Already expired", "expires_at": past},
    )
    missing_user = client.get(f"/api/v1/auth/users/{unknown}/api-keys")
    missing_key = client.delete(f"/api/v1/auth/api-keys/{unknown}")

    assert expired.status_code == 409
    assert missing_user.status_code == 404
    assert missing_key.status_code == 404
