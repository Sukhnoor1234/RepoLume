"""Unit tests for deterministic repository evidence retrieval."""

from repolume_api.analysis_schemas import RepositoryArchitectureResponse
from repolume_api.evidence_retrieval import retrieve_evidence


def _architecture() -> RepositoryArchitectureResponse:
    nodes = [
        {
            "id": "repository",
            "kind": "repository",
            "name": "repository",
            "language": None,
        },
        {
            "id": "module:auth",
            "kind": "module",
            "name": "auth_service",
            "language": "python",
            "location": {"path": "services/auth_service.py", "line": 1, "end_line": 80},
            "qualified_name": "services.auth_service",
            "detail": "Authentication helpers and token validation",
            "source_bytes": 1200,
            "line_count": 80,
        },
        {
            "id": "symbol:login",
            "kind": "symbol",
            "name": "login_user",
            "language": "python",
            "location": {"path": "services/auth_service.py", "line": 20, "end_line": 34},
            "qualified_name": "services.auth_service.login_user",
            "symbol_kind": "function",
            "detail": "Authenticates credentials and returns a session",
            "decorators": ["router.post"],
            "line_count": 15,
        },
        {
            "id": "module:orders",
            "kind": "module",
            "name": "orders",
            "language": "python",
            "location": {"path": "orders.py", "line": 1, "end_line": 40},
            "source_bytes": 600,
            "line_count": 40,
        },
    ]
    edges = [
        {
            "id": f"contains:{node['id']}",
            "kind": "contains",
            "source": "repository" if node["kind"] == "module" else "module:auth",
            "target": node["id"],
            "confidence": "confirmed",
            "location": node["location"],
        }
        for node in nodes[1:]
    ]
    return RepositoryArchitectureResponse.model_validate(
        {
            "schema_version": "1.0",
            "languages": ["python"],
            "nodes": nodes,
            "edges": edges,
            "diagnostics": [],
            "summary": {
                "language_count": 1,
                "node_count": 4,
                "edge_count": 3,
                "module_count": 2,
                "symbol_count": 1,
                "entry_point_count": 0,
                "external_dependency_count": 0,
                "dependency_count": 0,
                "diagnostic_count": 0,
            },
        }
    )


def test_ranks_name_and_path_matches_before_detail_only_matches() -> None:
    matches = retrieve_evidence(_architecture(), "Where is user authentication implemented?")

    assert [match.node.id for match in matches] == ["symbol:login", "module:auth"]
    assert matches[0].matched_terms == ("user", "auth")
    assert matches[0].score > matches[1].score


def test_splits_snake_case_and_ignores_question_stop_words() -> None:
    matches = retrieve_evidence(_architecture(), "How does login user work?")

    assert matches[0].node.id == "symbol:login"
    assert matches[0].matched_terms == ("login", "user")


def test_returns_empty_results_when_no_architecture_terms_match() -> None:
    assert retrieve_evidence(_architecture(), "Where is billing?") == ()
    assert retrieve_evidence(_architecture(), "Where is it?") == ()


def test_applies_limit_after_deterministic_ranking() -> None:
    matches = retrieve_evidence(_architecture(), "python", limit=2)

    assert len(matches) == 2
    assert [match.node.id for match in matches] == ["module:orders", "module:auth"]
