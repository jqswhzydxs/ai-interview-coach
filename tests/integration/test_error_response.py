from fastapi.testclient import TestClient

from app.main import app


def test_not_found_uses_uniform_error_response() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/missing", headers={"x-request-id": "err-req"})

    assert response.status_code == 404
    assert response.headers["x-request-id"] == "err-req"
    body = response.json()
    assert body == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Not found",
            "details": {},
        }
    }

