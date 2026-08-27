"""HTTP contract tests for repository analysis jobs."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from repolume_api.analyses import (
    AnalysisJobSnapshot,
    AnalysisNotCompleted,
    AnalysisNotFound,
)
from repolume_api.analysis_schemas import RepositoryArchitectureResponse
from repolume_api.config import Settings
from repolume_api.main import create_app
from repolume_api.repositories import RepositoryReference

_REPOSITORY = RepositoryReference(owner="octocat", repository="Hello-World", ref="main")
_QUEUED = AnalysisJobSnapshot(
    analysis_id="analysis_123",
    status="queued",
    repository=_REPOSITORY,
)
_ARCHITECTURE = RepositoryArchitectureResponse.model_validate(
    {
        "schema_version": "1.0",
        "languages": ["python"],
        "nodes": [
            {
                "id": "repository",
                "kind": "repository",
                "name": "repository",
                "language": None,
            },
            {
                "id": "module:app",
                "kind": "module",
                "name": "app",
                "language": "python",
                "location": {"path": "app.py", "line": 1, "end_line": 4},
                "source_bytes": 42,
                "line_count": 4,
            },
        ],
        "edges": [
            {
                "id": "contains:repository:module:app",
                "kind": "contains",
                "source": "repository",
                "target": "module:app",
                "confidence": "confirmed",
                "location": {"path": "app.py", "line": 1, "end_line": 4},
            }
        ],
        "diagnostics": [],
        "summary": {
            "language_count": 1,
            "node_count": 2,
            "edge_count": 1,
            "module_count": 1,
            "symbol_count": 0,
            "entry_point_count": 0,
            "external_dependency_count": 0,
            "dependency_count": 0,
            "diagnostic_count": 0,
        },
    }
)


class FakeAnalysisJobService:
    def __init__(self) -> None:
        self.submitted: list[RepositoryReference] = []
        self.snapshots = {"analysis_123": _QUEUED}
        self.architectures: dict[str, RepositoryArchitectureResponse] = {}

    def submit(self, repository: RepositoryReference) -> AnalysisJobSnapshot:
        self.submitted.append(repository)
        return replace(_QUEUED, repository=repository)

    def get(self, analysis_id: str) -> AnalysisJobSnapshot:
        try:
            return self.snapshots[analysis_id]
        except KeyError as exc:
            raise AnalysisNotFound from exc

    def get_architecture(self, analysis_id: str) -> RepositoryArchitectureResponse:
        snapshot = self.get(analysis_id)
        if snapshot.status != "completed":
            raise AnalysisNotCompleted
        return self.architectures[analysis_id]


def _client(service: FakeAnalysisJobService) -> TestClient:
    return TestClient(
        create_app(
            Settings(environment="test"),
            analysis_job_service=service,
        )
    )


def test_submit_accepts_and_normalizes_repository() -> None:
    service = FakeAnalysisJobService()

    with _client(service) as client:
        response = client.post(
            "/v1/analyses",
            json={
                "repository_url": "https://github.com/octocat/Hello-World.git",
                "ref": "main",
            },
        )

    assert response.status_code == 202
    assert response.json() == {"analysis_id": "analysis_123", "status": "queued"}
    assert service.submitted == [_REPOSITORY]


def test_submit_rejects_invalid_reference_before_service_call() -> None:
    service = FakeAnalysisJobService()
    submitted_url = "https://user:secret@github.com/octocat/Hello-World"

    with _client(service) as client:
        response = client.post(
            "/v1/analyses",
            json={"repository_url": submitted_url},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "repository_url_invalid"
    assert submitted_url not in response.text
    assert service.submitted == []


def test_submit_is_safely_unavailable_without_job_adapter() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post(
            "/v1/analyses",
            json={"repository_url": "https://github.com/octocat/Hello-World"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "analysis_service_unavailable",
            "message": "Repository analysis is temporarily unavailable.",
        }
    }


def test_inspect_returns_queued_job_without_embedded_result() -> None:
    service = FakeAnalysisJobService()

    with _client(service) as client:
        response = client.get("/v1/analyses/analysis_123")

    assert response.status_code == 200
    assert response.json() == {
        "analysis_id": "analysis_123",
        "status": "queued",
        "repository": {
            "provider": "github",
            "owner": "octocat",
            "repository": "Hello-World",
            "canonical_url": "https://github.com/octocat/Hello-World",
            "ref": "main",
        },
        "result_available": False,
        "failure": None,
    }


def test_inspect_returns_safe_failed_job_details() -> None:
    service = FakeAnalysisJobService()
    service.snapshots["analysis_123"] = AnalysisJobSnapshot(
        analysis_id="analysis_123",
        status="failed",
        repository=_REPOSITORY,
        failure_code="repository_not_found",
        failure_message="The GitHub repository or ref was not found.",
    )

    with _client(service) as client:
        response = client.get("/v1/analyses/analysis_123")

    assert response.status_code == 200
    assert response.json()["failure"] == {
        "code": "repository_not_found",
        "message": "The GitHub repository or ref was not found.",
    }
    assert response.json()["result_available"] is False


def test_inspect_maps_unknown_analysis_to_stable_not_found_error() -> None:
    service = FakeAnalysisJobService()

    with _client(service) as client:
        response = client.get("/v1/analyses/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "analysis_not_found",
            "message": "The requested analysis was not found.",
        }
    }


def test_architecture_returns_completed_graph() -> None:
    service = FakeAnalysisJobService()
    service.snapshots["analysis_123"] = replace(
        _QUEUED,
        status="completed",
        result_available=True,
    )
    service.architectures["analysis_123"] = _ARCHITECTURE

    with _client(service) as client:
        response = client.get("/v1/analyses/analysis_123/architecture")

    assert response.status_code == 200
    assert response.json() == _ARCHITECTURE.model_dump(mode="json")
    assert response.json()["summary"] == {
        "language_count": 1,
        "node_count": 2,
        "edge_count": 1,
        "module_count": 1,
        "symbol_count": 0,
        "entry_point_count": 0,
        "external_dependency_count": 0,
        "dependency_count": 0,
        "diagnostic_count": 0,
    }


def test_architecture_rejects_active_analysis() -> None:
    service = FakeAnalysisJobService()

    with _client(service) as client:
        response = client.get("/v1/analyses/analysis_123/architecture")

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "analysis_not_completed",
        "message": "Architecture is available only after analysis completes.",
    }


def test_evidence_query_returns_ranked_source_matches() -> None:
    service = FakeAnalysisJobService()
    service.snapshots["analysis_123"] = replace(
        _QUEUED,
        status="completed",
        result_available=True,
    )
    service.architectures["analysis_123"] = _ARCHITECTURE

    with _client(service) as client:
        response = client.post(
            "/v1/analyses/analysis_123/evidence-query",
            json={"question": "Where is the app module?"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "question": "Where is the app module?",
        "matches": [
            {
                "node_id": "module:app",
                "kind": "module",
                "name": "app",
                "language": "python",
                "location": {"path": "app.py", "line": 1, "end_line": 4},
                "confidence": "confirmed",
                "score": 7,
                "matched_terms": ["app", "module"],
                "relationship_count": 1,
            }
        ],
    }


def test_evidence_query_rejects_active_analysis() -> None:
    service = FakeAnalysisJobService()

    with _client(service) as client:
        response = client.post(
            "/v1/analyses/analysis_123/evidence-query",
            json={"question": "Where is authentication?"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "analysis_not_completed"


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "  "},
        {"question": "valid question", "limit": 0},
        {"question": "valid question", "limit": 11},
        {"question": "valid question", "unexpected": True},
    ],
)
def test_evidence_query_rejects_invalid_payload(payload: dict[str, object]) -> None:
    service = FakeAnalysisJobService()

    with _client(service) as client:
        response = client.post("/v1/analyses/analysis_123/evidence-query", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_analysis_id_rejects_unsafe_path_values() -> None:
    service = FakeAnalysisJobService()

    with _client(service) as client:
        response = client.get("/v1/analyses/not.valid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_openapi_documents_analysis_contracts() -> None:
    service = FakeAnalysisJobService()

    with _client(service) as client:
        document = client.get("/openapi.json").json()

    assert document["paths"]["/v1/analyses"]["post"]["responses"]["202"]
    assert document["paths"]["/v1/analyses/{analysis_id}"]["get"]
    assert document["paths"]["/v1/analyses/{analysis_id}/architecture"]["get"]
    assert document["paths"]["/v1/analyses/{analysis_id}/evidence-query"]["post"]


def test_architecture_schema_rejects_undocumented_or_negative_values() -> None:
    undocumented = _ARCHITECTURE.model_dump(mode="json")
    undocumented["unexpected"] = True
    with pytest.raises(ValidationError):
        RepositoryArchitectureResponse.model_validate(undocumented)

    negative_count = _ARCHITECTURE.model_dump(mode="json")
    negative_count["summary"]["node_count"] = -1
    with pytest.raises(ValidationError):
        RepositoryArchitectureResponse.model_validate(negative_count)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"analysis_id": " "}, "analysis_id must not be empty"),
        ({"status": "unknown"}, "unknown analysis status"),
        ({"failure_code": "code"}, "failure code and message must be provided together"),
        (
            {"status": "failed", "failure_code": None, "failure_message": None},
            "failed analyses require safe failure details",
        ),
        ({"result_available": True}, "result availability must match completed status"),
    ],
)
def test_job_snapshot_rejects_inconsistent_state(
    changes: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(_QUEUED, **changes)
