"""Tests for deterministic, non-executing Python repository analysis."""

import json
from pathlib import Path

import pytest

from repolume_worker.analysis_models import Confidence, DependencyKind, SymbolKind
from repolume_worker.errors import RepositoryAnalysisError
from repolume_worker.limits import AnalysisLimits
from repolume_worker.python_analysis import PythonRepositoryAnalyzer

_FIXTURE = Path(__file__).parent / "fixtures" / "python_shop"


def _write_python(path: Path, source: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(source, bytes):
        path.write_bytes(source)
    else:
        path.write_text(source, encoding="utf-8")


def test_analyzes_src_layout_fixture() -> None:
    artifact = PythonRepositoryAnalyzer().analyze(_FIXTURE)

    assert artifact.schema_version == "1.0"
    assert artifact.language == "python"
    assert artifact.summary.module_count == 7
    assert artifact.summary.symbol_count == 5
    assert artifact.summary.local_dependency_count == 4
    assert artifact.summary.external_dependency_count == 4
    assert artifact.summary.entry_point_count == 2
    assert artifact.summary.diagnostic_count == 0
    assert [module.name for module in artifact.modules] == [
        "shop",
        "shop.__main__",
        "shop.main",
        "shop.models",
        "shop.models.order",
        "shop.services",
        "shop.services.orders",
    ]


def test_uses_the_nearest_nested_src_directory_as_source_root(tmp_path: Path) -> None:
    _write_python(tmp_path / "packages" / "catalog" / "src" / "catalog" / "__init__.py", "")
    _write_python(
        tmp_path / "packages" / "catalog" / "src" / "catalog" / "service.py",
        "from . import helpers\n",
    )
    _write_python(
        tmp_path / "packages" / "catalog" / "src" / "catalog" / "helpers.py",
        "VALUE = 1\n",
    )

    artifact = PythonRepositoryAnalyzer().analyze(tmp_path)

    assert [module.name for module in artifact.modules] == [
        "catalog",
        "catalog.helpers",
        "catalog.service",
    ]
    local = next(
        dependency for dependency in artifact.dependencies if dependency.source == "catalog.service"
    )
    assert local.target == "catalog.helpers"
    assert local.kind is DependencyKind.LOCAL


def test_reports_ambiguous_module_names_without_building_colliding_nodes(
    tmp_path: Path,
) -> None:
    _write_python(tmp_path / "services" / "auth" / "src" / "app" / "__init__.py", "")
    _write_python(tmp_path / "services" / "orders" / "src" / "app" / "__init__.py", "")

    artifact = PythonRepositoryAnalyzer().analyze(tmp_path)

    assert artifact.modules == ()
    assert [diagnostic.code for diagnostic in artifact.diagnostics] == [
        "python_module_ambiguous",
        "python_module_ambiguous",
    ]
    assert [diagnostic.path for diagnostic in artifact.diagnostics] == [
        "services/auth/src/app/__init__.py",
        "services/orders/src/app/__init__.py",
    ]


def test_deduplicates_repeated_import_relationships(tmp_path: Path) -> None:
    _write_python(tmp_path / "module.py", "import json\nimport json\n")

    artifact = PythonRepositoryAnalyzer().analyze(tmp_path)

    assert len(artifact.dependencies) == 1
    dependency = artifact.dependencies[0]
    assert dependency.source == "module"
    assert dependency.target == "json"
    assert dependency.location.line == 1


def test_resolves_local_and_external_imports_with_evidence() -> None:
    artifact = PythonRepositoryAnalyzer().analyze(_FIXTURE)
    dependencies = {
        (dependency.source, dependency.target): dependency for dependency in artifact.dependencies
    }

    local = dependencies[("shop.services.orders", "shop.models.order")]
    assert local.kind is DependencyKind.LOCAL
    assert local.confidence is Confidence.CONFIRMED
    assert local.location.path == "src/shop/services/orders.py"
    assert local.location.line == 3

    external = dependencies[("shop.main", "fastapi")]
    assert external.kind is DependencyKind.EXTERNAL
    assert external.confidence is Confidence.HEURISTIC
    assert external.location.line == 1


def test_extracts_top_level_symbols_and_decorators() -> None:
    artifact = PythonRepositoryAnalyzer().analyze(_FIXTURE)
    order_module = next(module for module in artifact.modules if module.name == "shop.models.order")
    order = order_module.symbols[0]

    assert order.name == "Order"
    assert order.qualified_name == "shop.models.order.Order"
    assert order.kind is SymbolKind.CLASS
    assert order.decorators == ("dataclass",)
    assert order.location.line == 6

    main_module = next(module for module in artifact.modules if module.name == "shop.main")
    assert [symbol.name for symbol in main_module.symbols] == ["create_app", "main"]
    assert "submit_order" not in {symbol.name for symbol in main_module.symbols}


def test_finds_confirmed_entry_points() -> None:
    artifact = PythonRepositoryAnalyzer().analyze(_FIXTURE)

    assert [(entry.module, entry.kind, entry.confidence) for entry in artifact.entry_points] == [
        ("shop.__main__", "module_entry", Confidence.CONFIRMED),
        ("shop.main", "main_guard", Confidence.CONFIRMED),
    ]


def test_marks_an_unguarded_main_function_as_heuristic(tmp_path: Path) -> None:
    _write_python(tmp_path / "cli.py", "def main():\n    return 0\n")

    artifact = PythonRepositoryAnalyzer().analyze(tmp_path)

    assert len(artifact.entry_points) == 1
    assert artifact.entry_points[0].kind == "main_function"
    assert artifact.entry_points[0].confidence is Confidence.HEURISTIC


def test_returns_stable_json_without_absolute_paths(tmp_path: Path) -> None:
    _write_python(tmp_path / "z.py", "import json\n")
    _write_python(tmp_path / "a.py", "class Example:\n    pass\n")
    analyzer = PythonRepositoryAnalyzer()

    first = analyzer.analyze(tmp_path).to_json()
    second = analyzer.analyze(tmp_path).to_json()

    assert first == second
    assert str(tmp_path) not in first
    assert json.loads(first)["modules"][0]["path"] == "a.py"


def test_does_not_execute_repository_source(tmp_path: Path) -> None:
    marker = tmp_path / "executed.txt"
    _write_python(
        tmp_path / "dangerous.py",
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
    )

    artifact = PythonRepositoryAnalyzer().analyze(tmp_path)

    assert artifact.summary.module_count == 1
    assert not marker.exists()


@pytest.mark.parametrize("ignored_directory", [".venv", "vendor", "node_modules", "__pycache__"])
def test_ignores_generated_and_dependency_directories(
    tmp_path: Path, ignored_directory: str
) -> None:
    _write_python(tmp_path / "app.py", "VALUE = 1\n")
    _write_python(tmp_path / ignored_directory / "ignored.py", "VALUE = 2\n")

    artifact = PythonRepositoryAnalyzer().analyze(tmp_path)

    assert [module.path for module in artifact.modules] == ["app.py"]


def test_reports_syntax_errors_and_continues(tmp_path: Path) -> None:
    _write_python(tmp_path / "broken.py", "def broken(:\n")
    _write_python(tmp_path / "healthy.py", "def healthy():\n    return True\n")

    artifact = PythonRepositoryAnalyzer().analyze(tmp_path)

    assert [module.name for module in artifact.modules] == ["healthy"]
    assert artifact.diagnostics[0].code == "python_syntax_error"
    assert artifact.diagnostics[0].path == "broken.py"
    assert artifact.diagnostics[0].line == 1


def test_reports_unsupported_source_encoding_and_continues(tmp_path: Path) -> None:
    _write_python(tmp_path / "invalid.py", b"# coding: unknown-codec\nVALUE = 1\n")
    _write_python(tmp_path / "healthy.py", "VALUE = 2\n")

    artifact = PythonRepositoryAnalyzer().analyze(tmp_path)

    assert artifact.summary.module_count == 1
    assert artifact.diagnostics[0].code == "source_decode_failed"
    assert artifact.diagnostics[0].path == "invalid.py"


def test_enforces_python_file_count_limit(tmp_path: Path) -> None:
    _write_python(tmp_path / "one.py", "ONE = 1\n")
    _write_python(tmp_path / "two.py", "TWO = 2\n")
    analyzer = PythonRepositoryAnalyzer(
        AnalysisLimits(max_python_files=1, max_total_source_bytes=100, max_single_source_bytes=50)
    )

    with pytest.raises(RepositoryAnalysisError) as raised:
        analyzer.analyze(tmp_path)

    assert raised.value.code == "analysis_limit_exceeded"


def test_enforces_single_source_file_limit(tmp_path: Path) -> None:
    _write_python(tmp_path / "large.py", "VALUE = 'too large'\n")
    analyzer = PythonRepositoryAnalyzer(
        AnalysisLimits(max_single_source_bytes=5, max_total_source_bytes=10)
    )

    with pytest.raises(RepositoryAnalysisError) as raised:
        analyzer.analyze(tmp_path)

    assert raised.value.code == "analysis_limit_exceeded"


def test_enforces_total_source_limit(tmp_path: Path) -> None:
    _write_python(tmp_path / "one.py", "ONE = 1\n")
    _write_python(tmp_path / "two.py", "TWO = 2\n")
    analyzer = PythonRepositoryAnalyzer(
        AnalysisLimits(max_single_source_bytes=10, max_total_source_bytes=15)
    )

    with pytest.raises(RepositoryAnalysisError) as raised:
        analyzer.analyze(tmp_path)

    assert raised.value.code == "analysis_limit_exceeded"


def test_enforces_source_path_depth_limit(tmp_path: Path) -> None:
    _write_python(tmp_path / "one" / "two" / "module.py", "VALUE = 1\n")
    analyzer = PythonRepositoryAnalyzer(AnalysisLimits(max_path_depth=2))

    with pytest.raises(RepositoryAnalysisError) as raised:
        analyzer.analyze(tmp_path)

    assert raised.value.code == "analysis_limit_exceeded"


def test_requires_a_repository_source_directory(tmp_path: Path) -> None:
    with pytest.raises(RepositoryAnalysisError) as raised:
        PythonRepositoryAnalyzer().analyze(tmp_path / "missing")

    assert raised.value.code == "repository_source_missing"


def test_empty_repository_produces_an_empty_artifact(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# No Python\n", encoding="utf-8")

    artifact = PythonRepositoryAnalyzer().analyze(tmp_path)

    assert artifact.modules == ()
    assert artifact.dependencies == ()
    assert artifact.summary.module_count == 0
