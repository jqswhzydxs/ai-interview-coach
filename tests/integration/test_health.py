from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok_with_request_id() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "ok"
    assert body["data"]["app_name"] == "ai-interview-coach"
    assert body["data"]["environment"] == "test"
    assert body["message"] == "ok"
    assert body["request_id"]
    assert response.headers["x-request-id"] == body["request_id"]


def test_health_respects_incoming_request_id() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health", headers={"x-request-id": "test-request"})

    assert response.status_code == 200
    assert response.json()["request_id"] == "test-request"
    assert response.headers["x-request-id"] == "test-request"
