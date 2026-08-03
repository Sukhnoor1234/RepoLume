"""Tests for deterministic language-neutral architecture composition."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from repolume_worker.analysis_models import Confidence, DependencyKind, SymbolKind
from repolume_worker.architecture import RepositoryArchitectureComposer
from repolume_worker.architecture_models import (
    ArchitectureEdgeKind,
    ArchitectureNodeKind,
)
from repolume_worker.python_analysis import PythonRepositoryAnalyzer
from repolume_worker.typescript_analysis import TypeScriptRepositoryAnalyzer

_FIXTURE = Path(__file__).parent / "fixtures" / "mixed_repository"


def _artifacts(root: Path = _FIXTURE):
    return (
        PythonRepositoryAnalyzer().analyze(root),
        TypeScriptRepositoryAnalyzer().analyze(root),
    )


def _compose(root: Path = _FIXTURE):
    return RepositoryArchitectureComposer().compose(_artifacts(root))


def test_composes_mixed_repository_summary() -> None:
    artifact = _compose()

    assert artifact.schema_version == "1.0"
    assert artifact.languages == ("python", "typescript-javascript")
    assert artifact.summary.language_count == 2
    assert artifact.summary.node_count == 13
    assert artifact.summary.edge_count == 14
    assert artifact.summary.module_count == 4
    assert artifact.summary.symbol_count == 4
    assert artifact.summary.entry_point_count == 2
    assert artifact.summary.external_dependency_count == 2
    assert artifact.summary.dependency_count == 4
    assert artifact.summary.diagnostic_count == 0


def test_creates_repository_and_language_neutral_module_nodes() -> None:
    artifact = _compose()
    nodes = {node.id: node for node in artifact.nodes}

    assert nodes["repository"].kind is ArchitectureNodeKind.REPOSITORY
    assert nodes["repository"].language is None

    python_module = nodes["module:python:backend%2Fapp.py"]
    script_module = nodes["module:typescript-javascript:frontend%2Fapp.ts"]

    assert python_module.kind is ArchitectureNodeKind.MODULE
    assert python_module.name == "backend.app"
    assert python_module.language == "python"
    assert python_module.location.path == "backend/app.py"
    assert python_module.source_bytes == (_FIXTURE / "backend" / "app.py").stat().st_size
    assert python_module.line_count == 11

    assert script_module.kind is ArchitectureNodeKind.MODULE
    assert script_module.name == "frontend.app"
    assert script_module.language == "typescript"
    assert script_module.location.path == "frontend/app.ts"


def test_namespaces_same_module_names_by_language_and_path(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "app.ts").write_text("export function run() {}\n", encoding="utf-8")

    artifact = _compose(tmp_path)
    modules = [node for node in artifact.nodes if node.kind is ArchitectureNodeKind.MODULE]

    assert {node.name for node in modules} == {"app"}
    assert {node.id for node in modules} == {
        "module:python:app.py",
        "module:typescript-javascript:app.ts",
    }


def test_creates_symbol_nodes_and_contains_edges() -> None:
    artifact = _compose()
    nodes = {node.id: node for node in artifact.nodes}
    edges = {(edge.kind, edge.source, edge.target): edge for edge in artifact.edges}

    service = nodes["symbol:python:backend%2Fservice.py:1:Service"]

    assert service.kind is ArchitectureNodeKind.SYMBOL
    assert service.name == "Service"
    assert service.qualified_name == "backend.service.Service"
    assert service.symbol_kind is SymbolKind.CLASS
    assert service.confidence is Confidence.CONFIRMED
    assert (
        ArchitectureEdgeKind.CONTAINS,
        "module:python:backend%2Fservice.py",
        service.id,
    ) in edges
    assert (
        ArchitectureEdgeKind.CONTAINS,
        "repository",
        "module:python:backend%2Fservice.py",
    ) in edges


def test_maps_local_and_external_dependencies_to_graph_nodes() -> None:
    artifact = _compose()
    nodes = {node.id: node for node in artifact.nodes}
    edges = {(edge.source, edge.target): edge for edge in artifact.edges}

    local = edges[
        (
            "module:python:backend%2Fapp.py",
            "module:python:backend%2Fservice.py",
        )
    ]
    external = edges[
        (
            "module:typescript-javascript:frontend%2Fapp.ts",
            "external:typescript-javascript:react",
        )
    ]

    assert local.kind is ArchitectureEdgeKind.DEPENDS_ON
    assert local.confidence is Confidence.CONFIRMED
    assert local.location.path == "backend/app.py"
    assert nodes[local.target].kind is ArchitectureNodeKind.MODULE

    assert external.kind is ArchitectureEdgeKind.DEPENDS_ON
    assert external.confidence is Confidence.HEURISTIC
    assert external.location.path == "frontend/app.ts"
    assert nodes[external.target].kind is ArchitectureNodeKind.EXTERNAL_DEPENDENCY
    assert nodes[external.target].name == "react"


def test_namespaces_external_dependencies_by_language(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("import shared\n", encoding="utf-8")
    (tmp_path / "app.ts").write_text('import "shared";\n', encoding="utf-8")

    artifact = _compose(tmp_path)
    external = {
        node.id: node
        for node in artifact.nodes
        if node.kind is ArchitectureNodeKind.EXTERNAL_DEPENDENCY
    }

    assert set(external) == {
        "external:python:shared",
        "external:typescript-javascript:shared",
    }


def test_preserves_entry_point_evidence_and_confidence() -> None:
    artifact = _compose()
    entries = {
        (node.language, node.detail): node
        for node in artifact.nodes
        if node.kind is ArchitectureNodeKind.ENTRY_POINT
    }

    python_entry = entries[("python", "main_guard")]
    script_entry = entries[("typescript", "main_function")]

    assert python_entry.confidence is Confidence.CONFIRMED
    assert python_entry.location.path == "backend/app.py"
    assert python_entry.location.line == 10
    assert script_entry.confidence is Confidence.HEURISTIC
    assert script_entry.location.path == "frontend/app.ts"


def test_preserves_symbol_decorators(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text(
        "@entity\nclass Model:\n    pass\n",
        encoding="utf-8",
    )

    artifact = _compose(tmp_path)
    model = next(
        node
        for node in artifact.nodes
        if node.kind is ArchitectureNodeKind.SYMBOL and node.name == "Model"
    )

    assert model.decorators == ("entity",)


def test_every_edge_references_existing_nodes() -> None:
    artifact = _compose()
    node_ids = {node.id for node in artifact.nodes}

    assert all(edge.source in node_ids and edge.target in node_ids for edge in artifact.edges)


def test_output_is_stable_regardless_of_artifact_order() -> None:
    python, script = _artifacts()
    composer = RepositoryArchitectureComposer()

    first = composer.compose((python, script)).to_json()
    second = composer.compose((script, python)).to_json()

    assert first == second
    assert str(_FIXTURE.resolve()) not in first
    assert json.loads(first)["nodes"][0]["id"].startswith("entry:")


def test_preserves_diagnostics_with_language_context(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    (tmp_path / "broken.ts").write_text("export const = ;\n", encoding="utf-8")

    artifact = _compose(tmp_path)

    assert [
        (diagnostic.language, diagnostic.code, diagnostic.path)
        for diagnostic in artifact.diagnostics
    ] == [
        ("python", "python_syntax_error", "broken.py"),
        ("typescript-javascript", "script_syntax_error", "broken.ts"),
    ]
    assert artifact.summary.diagnostic_count == 2


def test_omits_languages_from_empty_analyzer_artifacts() -> None:
    python = PythonRepositoryAnalyzer().analyze(Path(__file__).parent / "fixtures" / "python_shop")
    scripts = TypeScriptRepositoryAnalyzer().analyze(
        Path(__file__).parent / "fixtures" / "python_shop"
    )

    artifact = RepositoryArchitectureComposer().compose((python, scripts))

    assert scripts.modules == ()
    assert artifact.languages == ("python",)
    assert artifact.summary.language_count == 1


def test_source_empty_repository_has_no_detected_languages(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Empty\n", encoding="utf-8")

    artifact = _compose(tmp_path)

    assert artifact.languages == ()
    assert artifact.summary.language_count == 0
    assert [node.id for node in artifact.nodes] == ["repository"]


def test_empty_composition_produces_only_the_repository_root() -> None:
    artifact = RepositoryArchitectureComposer().compose(())

    assert artifact.languages == ()
    assert [node.id for node in artifact.nodes] == ["repository"]
    assert artifact.edges == ()
    assert artifact.summary.node_count == 1
    assert artifact.summary.edge_count == 0


def test_rejects_duplicate_language_artifacts() -> None:
    python, _ = _artifacts()

    with pytest.raises(ValueError, match="Only one artifact"):
        RepositoryArchitectureComposer().compose((python, python))


def test_rejects_unsupported_analysis_schema_versions() -> None:
    python, script = _artifacts()
    unsupported = replace(script, schema_version="2.0")

    with pytest.raises(ValueError, match="unsupported schema"):
        RepositoryArchitectureComposer().compose((python, unsupported))


def test_rejects_a_missing_confirmed_local_target() -> None:
    python, script = _artifacts()
    local = next(
        dependency for dependency in python.dependencies if dependency.kind is DependencyKind.LOCAL
    )
    invalid = replace(
        python,
        dependencies=(replace(local, target="missing.module"),),
    )

    with pytest.raises(ValueError, match="local dependency target"):
        RepositoryArchitectureComposer().compose((invalid, script))
