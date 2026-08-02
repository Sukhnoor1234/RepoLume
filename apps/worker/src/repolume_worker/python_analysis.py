"""Bounded, deterministic static analysis for Python repository snapshots."""

import ast
import io
import os
import tokenize
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from repolume_worker.analysis_models import (
    AnalysisDiagnostic,
    AnalysisSummary,
    Confidence,
    Dependency,
    DependencyKind,
    EntryPoint,
    PythonAnalysisArtifact,
    PythonModule,
    SourceLocation,
    Symbol,
    SymbolKind,
)
from repolume_worker.errors import RepositoryAnalysisError
from repolume_worker.limits import AnalysisLimits

_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "site-packages",
        "vendor",
        "venv",
    }
)


@dataclass(frozen=True, slots=True)
class _ParsedModule:
    module: PythonModule
    tree: ast.Module
    is_package: bool


def _location(path: str, node: ast.AST) -> SourceLocation:
    line = getattr(node, "lineno", 1)
    return SourceLocation(path=path, line=line, end_line=getattr(node, "end_lineno", line))


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _dotted_name(node.func)
    return None


def _module_name(relative_path: PurePosixPath) -> str:
    parts = list(relative_path.with_suffix("").parts)
    source_root_indexes = [index for index, part in enumerate(parts[:-1]) if part == "src"]
    if source_root_indexes:
        parts = parts[source_root_indexes[-1] + 1 :]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or "__root__"


def _is_main_guard(node: ast.If) -> bool:
    comparison = node.test
    if not isinstance(comparison, ast.Compare) or len(comparison.ops) != 1:
        return False
    if not isinstance(comparison.ops[0], ast.Eq) or len(comparison.comparators) != 1:
        return False
    left, right = comparison.left, comparison.comparators[0]
    return (
        isinstance(left, ast.Name)
        and left.id == "__name__"
        and isinstance(right, ast.Constant)
        and right.value == "__main__"
    ) or (
        isinstance(right, ast.Name)
        and right.id == "__name__"
        and isinstance(left, ast.Constant)
        and left.value == "__main__"
    )


def _resolve_relative_base(module: _ParsedModule, imported: str | None, level: int) -> str:
    package_parts = module.module.name.split(".")
    if not module.is_package:
        package_parts = package_parts[:-1]
    steps_up = max(level - 1, 0)
    if steps_up > len(package_parts):
        return imported or ""
    base_parts = package_parts[: len(package_parts) - steps_up]
    if imported:
        base_parts.extend(imported.split("."))
    return ".".join(part for part in base_parts if part)


def _classify_target(
    target: str, local_modules: frozenset[str]
) -> tuple[str, DependencyKind, Confidence]:
    if target in local_modules:
        return target, DependencyKind.LOCAL, Confidence.CONFIRMED
    return target.split(".")[0], DependencyKind.EXTERNAL, Confidence.HEURISTIC


class PythonRepositoryAnalyzer:
    """Analyze Python syntax without importing, building, or running source code."""

    def __init__(self, limits: AnalysisLimits | None = None) -> None:
        self.limits = limits or AnalysisLimits()

    def _discover(self, root: Path) -> tuple[Path, ...]:
        discovered: list[Path] = []
        total_bytes = 0

        for current_root, directory_names, file_names in os.walk(root, followlinks=False):
            current_path = Path(current_root)
            directory_names[:] = sorted(
                name
                for name in directory_names
                if name not in _IGNORED_DIRECTORIES and not (current_path / name).is_symlink()
            )
            for file_name in sorted(file_names):
                source_path = current_path / file_name
                if source_path.suffix.casefold() != ".py" or source_path.is_symlink():
                    continue

                relative_path = PurePosixPath(source_path.relative_to(root).as_posix())
                if len(relative_path.parts) > self.limits.max_path_depth:
                    raise RepositoryAnalysisError(
                        "analysis_limit_exceeded",
                        "A Python source path is deeper than the supported analysis limit.",
                    )
                if len(relative_path.as_posix()) > self.limits.max_path_length:
                    raise RepositoryAnalysisError(
                        "analysis_limit_exceeded",
                        "A Python source path is longer than the supported analysis limit.",
                    )
                try:
                    source_bytes = source_path.stat().st_size
                except OSError as exc:
                    raise RepositoryAnalysisError(
                        "source_read_failed", "A Python source file could not be inspected."
                    ) from exc
                if source_bytes > self.limits.max_single_source_bytes:
                    raise RepositoryAnalysisError(
                        "analysis_limit_exceeded",
                        "A Python source file is beyond the supported analysis limit.",
                    )

                total_bytes += source_bytes
                discovered.append(source_path)
                if len(discovered) > self.limits.max_python_files:
                    raise RepositoryAnalysisError(
                        "analysis_limit_exceeded",
                        "The repository contains more Python files than can be analyzed.",
                    )
                if total_bytes > self.limits.max_total_source_bytes:
                    raise RepositoryAnalysisError(
                        "analysis_limit_exceeded",
                        "The repository contains more Python source than can be analyzed.",
                    )

        return tuple(discovered)

    @staticmethod
    def _read_source(path: Path) -> tuple[str, int]:
        try:
            content = path.read_bytes()
            encoding, _ = tokenize.detect_encoding(io.BytesIO(content).readline)
            return content.decode(encoding), len(content)
        except (LookupError, OSError, SyntaxError, UnicodeError) as exc:
            raise RepositoryAnalysisError(
                "source_decode_failed", "A Python source file could not be decoded."
            ) from exc

    @staticmethod
    def _symbols(module_name: str, path: str, tree: ast.Module) -> tuple[Symbol, ...]:
        symbols: list[Symbol] = []
        for node in tree.body:
            kind: SymbolKind | None = None
            if isinstance(node, ast.AsyncFunctionDef):
                kind = SymbolKind.ASYNC_FUNCTION
            elif isinstance(node, ast.FunctionDef):
                kind = SymbolKind.FUNCTION
            elif isinstance(node, ast.ClassDef):
                kind = SymbolKind.CLASS
            if kind is None:
                continue
            decorators = tuple(
                name for decorator in node.decorator_list if (name := _dotted_name(decorator))
            )
            symbols.append(
                Symbol(
                    name=node.name,
                    qualified_name=f"{module_name}.{node.name}",
                    kind=kind,
                    location=_location(path, node),
                    decorators=decorators,
                )
            )
        return tuple(symbols)

    def _parse_modules(
        self, root: Path, paths: tuple[Path, ...]
    ) -> tuple[tuple[_ParsedModule, ...], tuple[AnalysisDiagnostic, ...]]:
        parsed: list[_ParsedModule] = []
        diagnostics: list[AnalysisDiagnostic] = []
        for source_path in paths:
            relative = PurePosixPath(source_path.relative_to(root).as_posix())
            relative_text = relative.as_posix()
            try:
                source, source_bytes = self._read_source(source_path)
            except RepositoryAnalysisError as exc:
                diagnostics.append(
                    AnalysisDiagnostic(code=exc.code, message=exc.message, path=relative_text)
                )
                continue
            try:
                tree = ast.parse(source, filename=relative_text, type_comments=True)
            except SyntaxError as exc:
                diagnostics.append(
                    AnalysisDiagnostic(
                        code="python_syntax_error",
                        message="Python syntax could not be parsed.",
                        path=relative_text,
                        line=exc.lineno,
                    )
                )
                continue
            module_name = _module_name(relative)
            parsed.append(
                _ParsedModule(
                    module=PythonModule(
                        name=module_name,
                        path=relative_text,
                        source_bytes=source_bytes,
                        line_count=len(source.splitlines()),
                        symbols=self._symbols(module_name, relative_text, tree),
                    ),
                    tree=tree,
                    is_package=relative.name == "__init__.py",
                )
            )
        module_counts = Counter(item.module.name for item in parsed)
        ambiguous_names = {module_name for module_name, count in module_counts.items() if count > 1}
        if ambiguous_names:
            unambiguous: list[_ParsedModule] = []
            for item in parsed:
                if item.module.name in ambiguous_names:
                    diagnostics.append(
                        AnalysisDiagnostic(
                            code="python_module_ambiguous",
                            message="Multiple Python files resolve to the same module name.",
                            path=item.module.path,
                        )
                    )
                else:
                    unambiguous.append(item)
            parsed = unambiguous
        return tuple(parsed), tuple(diagnostics)

    @staticmethod
    def _dependencies(modules: tuple[_ParsedModule, ...]) -> tuple[Dependency, ...]:
        local_modules = frozenset(module.module.name for module in modules)
        dependencies: list[Dependency] = []
        seen: set[tuple[str, str, DependencyKind]] = set()

        for parsed in modules:
            for node in ast.walk(parsed.tree):
                targets: list[str] = []
                if isinstance(node, ast.Import):
                    targets.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    base = (
                        _resolve_relative_base(parsed, node.module, node.level)
                        if node.level
                        else (node.module or "")
                    )
                    for alias in node.names:
                        candidate = f"{base}.{alias.name}".strip(".")
                        targets.append(
                            candidate if candidate in local_modules else base or alias.name
                        )
                else:
                    continue

                for raw_target in targets:
                    if not raw_target:
                        continue
                    target, kind, confidence = _classify_target(raw_target, local_modules)
                    key = (parsed.module.name, target, kind)
                    if key in seen:
                        continue
                    seen.add(key)
                    dependencies.append(
                        Dependency(
                            source=parsed.module.name,
                            target=target,
                            kind=kind,
                            confidence=confidence,
                            location=_location(parsed.module.path, node),
                        )
                    )
        return tuple(
            sorted(
                dependencies,
                key=lambda item: (item.source, item.target, item.location.line, item.kind),
            )
        )

    @staticmethod
    def _entry_points(modules: tuple[_ParsedModule, ...]) -> tuple[EntryPoint, ...]:
        entries: list[EntryPoint] = []
        for parsed in modules:
            module = parsed.module
            if PurePosixPath(module.path).name == "__main__.py":
                entries.append(
                    EntryPoint(
                        module=module.name,
                        kind="module_entry",
                        confidence=Confidence.CONFIRMED,
                        location=SourceLocation(path=module.path, line=1, end_line=1),
                    )
                )
            has_main_guard = False
            for node in parsed.tree.body:
                if isinstance(node, ast.If) and _is_main_guard(node):
                    has_main_guard = True
                    entries.append(
                        EntryPoint(
                            module=module.name,
                            kind="main_guard",
                            confidence=Confidence.CONFIRMED,
                            location=_location(module.path, node),
                        )
                    )
            if not has_main_guard:
                main_symbol = next(
                    (symbol for symbol in module.symbols if symbol.name == "main"), None
                )
                if main_symbol is not None:
                    entries.append(
                        EntryPoint(
                            module=module.name,
                            kind="main_function",
                            confidence=Confidence.HEURISTIC,
                            location=main_symbol.location,
                        )
                    )
        return tuple(sorted(entries, key=lambda item: (item.module, item.location.line, item.kind)))

    def analyze(self, repository_root: Path) -> PythonAnalysisArtifact:
        """Return a deterministic Python artifact for an extracted repository."""

        root = repository_root.resolve()
        if not root.is_dir():
            raise RepositoryAnalysisError(
                "repository_source_missing", "The repository source directory is unavailable."
            )

        paths = self._discover(root)
        parsed, diagnostics = self._parse_modules(root, paths)
        modules = tuple(sorted((item.module for item in parsed), key=lambda item: item.path))
        dependencies = self._dependencies(parsed)
        entry_points = self._entry_points(parsed)
        symbol_count = sum(len(module.symbols) for module in modules)
        return PythonAnalysisArtifact(
            schema_version="1.0",
            language="python",
            modules=modules,
            dependencies=dependencies,
            entry_points=entry_points,
            diagnostics=tuple(sorted(diagnostics, key=lambda item: item.path)),
            summary=AnalysisSummary(
                module_count=len(modules),
                symbol_count=symbol_count,
                local_dependency_count=sum(
                    dependency.kind is DependencyKind.LOCAL for dependency in dependencies
                ),
                external_dependency_count=sum(
                    dependency.kind is DependencyKind.EXTERNAL for dependency in dependencies
                ),
                entry_point_count=len(entry_points),
                diagnostic_count=len(diagnostics),
            ),
        )
