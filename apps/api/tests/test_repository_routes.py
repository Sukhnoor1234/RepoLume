"""HTTP contract tests for repository preflight."""

from fastapi.testclient import TestClient

from repolume_api.config import Settings
from repolume_api.main import create_app


def test_preflight_returns_normalized_reference() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post(
            "/v1/repositories/preflight",
            json={
                "repository_url": "https://github.com/octocat/Hello-World.git",
                "ref": "main",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "provider": "github",
        "owner": "octocat",
        "repository": "Hello-World",
        "canonical_url": "https://github.com/octocat/Hello-World",
        "ref": "main",
    }


def test_preflight_returns_domain_error_without_echoing_input() -> None:
    submitted_url = "https://user:secret@github.com/owner/repository"

    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post(
            "/v1/repositories/preflight",
            json={"repository_url": submitted_url},
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "repository_url_invalid",
            "message": "Credentials are not allowed in repository URLs.",
        }
    }
    assert submitted_url not in response.text


def test_preflight_request_schema_rejects_missing_repository_url() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post("/v1/repositories/preflight", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_preflight_request_schema_rejects_unknown_fields() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post(
            "/v1/repositories/preflight",
            json={
                "repository_url": "https://github.com/owner/repository",
                "unexpected": True,
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
