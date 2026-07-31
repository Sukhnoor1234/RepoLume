from fastapi.testclient import TestClient

from repolume_api.config import Settings
from repolume_api.main import create_app


def test_unknown_route_uses_error_envelope() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
        }
    }


def test_validation_failure_uses_error_envelope() -> None:
    app = create_app(Settings(environment="test"))

    @app.get("/validate")
    async def validate(limit: int) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(app) as client:
        response = client.get("/validate", params={"limit": "invalid"})

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }
