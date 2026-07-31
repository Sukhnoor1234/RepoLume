from fastapi.testclient import TestClient

from repolume_api.config import Settings
from repolume_api.main import create_app


def test_health_reports_service_metadata() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "repolume-api",
        "version": "0.1.0",
        "environment": "test",
    }


def test_openapi_documents_health_endpoint() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
