"""Tests for deterministic TypeScript and JavaScript repository analysis."""

import json
from pathlib import Path

import pytest

from repolume_worker.analysis_models import Confidence, DependencyKind, SymbolKind
from repolume_worker.errors import RepositoryAnalysisError
from repolume_worker.limits import ScriptAnalysisLimits
from repolume_worker.typescript_analysis import TypeScriptRepositoryAnalyzer

_FIXTURE = Path(__file__).parent / "fixtures" / "typescript_shop"


def _write_script(path: Path, source: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(source, bytes):
        path.write_bytes(source)
    else:
        path.write_text(source, encoding="utf-8")


def test_analyzes_mixed_script_fixture() -> None:
    artifact = TypeScriptRepositoryAnalyzer().analyze(_FIXTURE)

    assert artifact.schema_version == "1.0"
    assert artifact.language == "typescript-javascript"
    assert artifact.summary.module_count == 9
    assert artifact.summary.symbol_count == 15
    assert artifact.summary.local_dependency_count == 7
    assert artifact.summary.external_dependency_count == 3
    assert artifact.summary.entry_point_count == 2
    assert artifact.summary.diagnostic_count == 0


def test_records_module_names_and_languages() -> None:
    artifact = TypeScriptRepositoryAnalyzer().analyze(_FIXTURE)

    assert [(module.name, module.language) for module in artifact.modules] == [
        ("app", "typescript"),
        ("components.OrderCard", "tsx"),
        ("config", "typescript"),
        ("__root__", "typescript"),
        ("lazy", "typescript"),
        ("models.order", "typescript"),
        ("routes.orders", "typescript"),
        ("services.orders", "typescript"),
        ("utils.format", "javascript"),
    ]


def test_resolves_relative_imports_with_runtime_extensions() -> None:
    artifact = TypeScriptRepositoryAnalyzer().analyze(_FIXTURE)
    dependencies = {
        (dependency.source, dependency.target): dependency for dependency in artifact.dependencies
    }

    orders = dependencies[("routes.orders", "services.orders")]

    assert orders.kind is DependencyKind.LOCAL
    assert orders.confidence is Confidence.CONFIRMED
    assert orders.location.path == "src/routes/orders.ts"
    assert orders.location.line == 3


def test_records_external_packages_and_scoped_package_roots(tmp_path: Path) -> None:
    _write_script(
        tmp_path / "module.ts",
        'import react from "react";\nimport client from "@scope/client/subpath";\n',
    )

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert [(item.target, item.kind) for item in artifact.dependencies] == [
        ("@scope/client", DependencyKind.EXTERNAL),
        ("react", DependencyKind.EXTERNAL),
    ]
    assert all(
        dependency.confidence is Confidence.HEURISTIC for dependency in artifact.dependencies
    )


def test_tracks_re_exports_as_dependencies() -> None:
    artifact = TypeScriptRepositoryAnalyzer().analyze(_FIXTURE)

    root_dependencies = {
        dependency.target for dependency in artifact.dependencies if dependency.source == "__root__"
    }

    assert root_dependencies == {"app", "models.order"}


def test_tracks_commonjs_and_dynamic_imports() -> None:
    artifact = TypeScriptRepositoryAnalyzer().analyze(_FIXTURE)
    dependencies = {
        (dependency.source, dependency.target): dependency for dependency in artifact.dependencies
    }

    assert dependencies[("app", "config")].location.line == 4
    assert dependencies[("lazy", "services.orders")].location.line == 1


def test_deduplicates_repeated_dependency_relationships(tmp_path: Path) -> None:
    _write_script(tmp_path / "module.ts", 'import "react";\nconst React = require("react");\n')

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert len(artifact.dependencies) == 1
    assert artifact.dependencies[0].target == "react"
    assert artifact.dependencies[0].location.line == 1


def test_extracts_typescript_symbol_kinds() -> None:
    artifact = TypeScriptRepositoryAnalyzer().analyze(_FIXTURE)
    modules = {module.name: module for module in artifact.modules}

    assert [(symbol.name, symbol.kind) for symbol in modules["models.order"].symbols] == [
        ("Order", SymbolKind.INTERFACE),
        ("OrderId", SymbolKind.TYPE_ALIAS),
        ("OrderStatus", SymbolKind.ENUM),
    ]
    assert [(symbol.name, symbol.kind) for symbol in modules["app"].symbols] == [
        ("config", SymbolKind.VARIABLE),
        ("app", SymbolKind.VARIABLE),
        ("createApp", SymbolKind.FUNCTION),
        ("start", SymbolKind.ASYNC_FUNCTION),
    ]
    assert modules["lazy"].symbols[0].kind is SymbolKind.ASYNC_FUNCTION


def test_extracts_class_decorators() -> None:
    artifact = TypeScriptRepositoryAnalyzer().analyze(_FIXTURE)
    routes = next(module for module in artifact.modules if module.name == "routes.orders")
    controller = next(symbol for symbol in routes.symbols if symbol.name == "OrderController")

    assert controller.kind is SymbolKind.CLASS
    assert controller.decorators == ("Controller",)
    assert controller.location.line == 8


def test_extracts_abstract_classes(tmp_path: Path) -> None:
    _write_script(tmp_path / "base.ts", "export abstract class Base {}\n")

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert [(symbol.name, symbol.kind) for symbol in artifact.modules[0].symbols] == [
        ("Base", SymbolKind.CLASS)
    ]


def test_extracts_ambient_declarations(tmp_path: Path) -> None:
    _write_script(
        tmp_path / "types.d.ts",
        "\n".join(
            (
                "declare function boot(): void;",
                "declare class Service {}",
                "declare const version: string;",
                "export declare abstract class Controller {}",
            )
        ),
    )

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert [(symbol.name, symbol.kind) for symbol in artifact.modules[0].symbols] == [
        ("boot", SymbolKind.FUNCTION),
        ("Service", SymbolKind.CLASS),
        ("version", SymbolKind.VARIABLE),
        ("Controller", SymbolKind.CLASS),
    ]
    assert not artifact.diagnostics


def test_parses_tsx_without_treating_jsx_as_an_error() -> None:
    artifact = TypeScriptRepositoryAnalyzer().analyze(_FIXTURE)
    component = next(module for module in artifact.modules if module.name == "components.OrderCard")

    assert component.language == "tsx"
    assert [symbol.name for symbol in component.symbols] == ["Props", "OrderCard"]
    assert not artifact.diagnostics


def test_finds_confirmed_and_heuristic_entry_points() -> None:
    artifact = TypeScriptRepositoryAnalyzer().analyze(_FIXTURE)

    assert [(entry.module, entry.kind, entry.confidence) for entry in artifact.entry_points] == [
        ("__root__", "conventional_entry_file", Confidence.HEURISTIC),
        ("app", "commonjs_main_guard", Confidence.CONFIRMED),
    ]


def test_marks_a_main_function_as_a_heuristic_entry(tmp_path: Path) -> None:
    _write_script(tmp_path / "cli.ts", "export function main() {}\n")

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert len(artifact.entry_points) == 1
    assert artifact.entry_points[0].kind == "main_function"
    assert artifact.entry_points[0].confidence is Confidence.HEURISTIC


def test_normalizes_declaration_file_module_names(tmp_path: Path) -> None:
    _write_script(tmp_path / "src" / "types.d.ts", "export interface User {}\n")

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert artifact.modules[0].name == "types"
    assert artifact.modules[0].symbols[0].name == "User"


def test_returns_stable_json_without_absolute_paths(tmp_path: Path) -> None:
    _write_script(tmp_path / "z.ts", 'import "react";\n')
    _write_script(tmp_path / "a.ts", "export class Example {}\n")
    analyzer = TypeScriptRepositoryAnalyzer()

    first = analyzer.analyze(tmp_path).to_json()
    second = analyzer.analyze(tmp_path).to_json()

    assert first == second
    assert str(tmp_path) not in first
    assert json.loads(first)["modules"][0]["path"] == "a.ts"


def test_does_not_execute_repository_source(tmp_path: Path) -> None:
    marker = tmp_path / "executed.txt"
    _write_script(
        tmp_path / "dangerous.js",
        f'require("node:fs").writeFileSync({str(marker)!r}, "executed");\n',
    )

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert artifact.summary.module_count == 1
    assert not marker.exists()


@pytest.mark.parametrize(
    "ignored_directory",
    [".next", "coverage", "node_modules", "vendor"],
)
def test_ignores_generated_and_dependency_directories(
    tmp_path: Path, ignored_directory: str
) -> None:
    _write_script(tmp_path / "app.ts", "export const value = 1;\n")
    _write_script(tmp_path / ignored_directory / "ignored.ts", "export const value = 2;\n")

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert [module.path for module in artifact.modules] == ["app.ts"]


def test_reports_syntax_errors_and_continues(tmp_path: Path) -> None:
    _write_script(tmp_path / "broken.ts", "export const = ;\n")
    _write_script(tmp_path / "healthy.ts", "export const healthy = true;\n")

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert [module.name for module in artifact.modules] == ["healthy"]
    assert artifact.diagnostics[0].code == "script_syntax_error"
    assert artifact.diagnostics[0].path == "broken.ts"
    assert artifact.diagnostics[0].line == 1


def test_reports_invalid_utf8_and_continues(tmp_path: Path) -> None:
    _write_script(tmp_path / "invalid.ts", b"export const value = '\xff';\n")
    _write_script(tmp_path / "healthy.ts", "export const healthy = true;\n")

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert artifact.summary.module_count == 1
    assert artifact.diagnostics[0].code == "source_decode_failed"
    assert artifact.diagnostics[0].path == "invalid.ts"


def test_reports_ambiguous_module_names_without_colliding_nodes(tmp_path: Path) -> None:
    _write_script(tmp_path / "services" / "auth" / "src" / "index.ts", "")
    _write_script(tmp_path / "services" / "orders" / "src" / "index.ts", "")

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert artifact.modules == ()
    assert [diagnostic.code for diagnostic in artifact.diagnostics] == [
        "script_module_ambiguous",
        "script_module_ambiguous",
    ]


def test_enforces_script_file_count_limit(tmp_path: Path) -> None:
    _write_script(tmp_path / "one.ts", "export const one = 1;\n")
    _write_script(tmp_path / "two.ts", "export const two = 2;\n")
    analyzer = TypeScriptRepositoryAnalyzer(
        ScriptAnalysisLimits(
            max_script_files=1,
            max_total_source_bytes=100,
            max_single_source_bytes=50,
        )
    )

    with pytest.raises(RepositoryAnalysisError) as raised:
        analyzer.analyze(tmp_path)

    assert raised.value.code == "analysis_limit_exceeded"


def test_enforces_single_source_file_limit(tmp_path: Path) -> None:
    _write_script(tmp_path / "large.ts", "export const value = 'too large';\n")
    analyzer = TypeScriptRepositoryAnalyzer(
        ScriptAnalysisLimits(max_single_source_bytes=5, max_total_source_bytes=10)
    )

    with pytest.raises(RepositoryAnalysisError) as raised:
        analyzer.analyze(tmp_path)

    assert raised.value.code == "analysis_limit_exceeded"


def test_enforces_total_source_limit(tmp_path: Path) -> None:
    _write_script(tmp_path / "one.ts", "const a=1;\n")
    _write_script(tmp_path / "two.ts", "const b=2;\n")
    analyzer = TypeScriptRepositoryAnalyzer(
        ScriptAnalysisLimits(max_single_source_bytes=20, max_total_source_bytes=20)
    )

    with pytest.raises(RepositoryAnalysisError) as raised:
        analyzer.analyze(tmp_path)

    assert raised.value.code == "analysis_limit_exceeded"


def test_enforces_source_path_depth_limit(tmp_path: Path) -> None:
    _write_script(tmp_path / "one" / "two" / "module.ts", "export const value = 1;\n")
    analyzer = TypeScriptRepositoryAnalyzer(ScriptAnalysisLimits(max_path_depth=2))

    with pytest.raises(RepositoryAnalysisError) as raised:
        analyzer.analyze(tmp_path)

    assert raised.value.code == "analysis_limit_exceeded"


def test_requires_a_repository_source_directory(tmp_path: Path) -> None:
    with pytest.raises(RepositoryAnalysisError) as raised:
        TypeScriptRepositoryAnalyzer().analyze(tmp_path / "missing")

    assert raised.value.code == "repository_source_missing"


def test_empty_repository_produces_an_empty_artifact(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# No scripts\n", encoding="utf-8")

    artifact = TypeScriptRepositoryAnalyzer().analyze(tmp_path)

    assert artifact.modules == ()
    assert artifact.dependencies == ()
    assert artifact.summary.module_count == 0
