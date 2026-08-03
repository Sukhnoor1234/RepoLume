"""Bounded static analysis for TypeScript and JavaScript repositories."""

import os
import posixpath
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import tree_sitter_typescript
from tree_sitter import Language, Node, Parser, Tree

from repolume_worker.analysis_models import (
    AnalysisDiagnostic,
    AnalysisSummary,
    Confidence,
    Dependency,
    DependencyKind,
    EntryPoint,
    ScriptAnalysisArtifact,
    ScriptModule,
    SourceLocation,
    Symbol,
    SymbolKind,
)
from repolume_worker.errors import RepositoryAnalysisError
from repolume_worker.limits import ScriptAnalysisLimits

_LANGUAGE_BY_EXTENSION = {
    ".cjs": "javascript",
    ".cts": "typescript",
    ".js": "javascript",
    ".jsx": "jsx",
    ".mjs": "javascript",
    ".mts": "typescript",
    ".ts": "typescript",
    ".tsx": "tsx",
}
_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".next",
        ".nuxt",
        ".svn",
        ".turbo",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "out",
        "vendor",
    }
)
_DECLARATION_TYPES = {
    "abstract_class_declaration": SymbolKind.CLASS,
    "class_declaration": SymbolKind.CLASS,
    "enum_declaration": SymbolKind.ENUM,
    "function_declaration": SymbolKind.FUNCTION,
    "function_signature": SymbolKind.FUNCTION,
    "generator_function_declaration": SymbolKind.FUNCTION,
    "interface_declaration": SymbolKind.INTERFACE,
    "type_alias_declaration": SymbolKind.TYPE_ALIAS,
}
_VARIABLE_DECLARATION_TYPES = {"lexical_declaration", "variable_declaration"}


@dataclass(frozen=True, slots=True)
class _ParsedScriptModule:
    module: ScriptModule
    tree: Tree
    source: bytes


def _source_location(path: str, node: Node) -> SourceLocation:
    return SourceLocation(
        path=path,
        line=node.start_point.row + 1,
        end_line=max(node.end_point.row + 1, node.start_point.row + 1),
    )


def _node_text(source: bytes, node: Node | None) -> str:
    if node is None:
        return ""
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _script_stem(path: PurePosixPath) -> str:
    name = path.name
    if name.casefold().endswith(".d.ts"):
        return name[:-5]
    return name[: -len(path.suffix)] if path.suffix else name


def _path_without_script_suffix(path: PurePosixPath) -> PurePosixPath:
    return path.with_name(_script_stem(path))


def _module_name(path: PurePosixPath) -> str:
    parts = list(_path_without_script_suffix(path).parts)
    source_root_indexes = [index for index, part in enumerate(parts[:-1]) if part == "src"]
    if source_root_indexes:
        parts = parts[source_root_indexes[-1] + 1 :]
    if parts and parts[-1] == "index":
        parts.pop()
    return ".".join(parts) or "__root__"


def _module_lookup_keys(path: str) -> tuple[str, ...]:
    logical = _path_without_script_suffix(PurePosixPath(path)).as_posix()
    keys = [logical]
    if logical.endswith("/index"):
        keys.append(logical[: -len("/index")])
    elif logical == "index":
        keys.append(".")
    return tuple(keys)


def _walk_named(node: Node):
    pending = [node]
    while pending:
        current = pending.pop()
        yield current
        pending.extend(reversed(current.named_children))


def _string_value(source: bytes, node: Node | None) -> str | None:
    raw = _node_text(source, node)
    if len(raw) < 2 or raw[0] not in {'"', "'", "`"} or raw[-1] != raw[0]:
        return None
    return raw[1:-1]


def _decorator_name(source: bytes, decorator: Node) -> str | None:
    raw = _node_text(source, decorator).strip()
    if raw.startswith("@"):
        raw = raw[1:]
    name = raw.split("(", 1)[0].strip()
    return name or None


def _external_package(specifier: str) -> str:
    parts = specifier.split("/")
    if specifier.startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def _relative_target_key(source_path: str, specifier: str) -> str:
    parent = PurePosixPath(source_path).parent.as_posix()
    combined = posixpath.normpath(posixpath.join(parent, specifier))
    return _path_without_script_suffix(PurePosixPath(combined)).as_posix()


def _resolve_dependency(
    source_path: str,
    specifier: str,
    local_modules: dict[str, str],
) -> tuple[str, DependencyKind, Confidence]:
    if specifier.startswith("."):
        target_key = _relative_target_key(source_path, specifier)
        target = local_modules.get(target_key) or local_modules.get(f"{target_key}/index")
        if target is not None:
            return target, DependencyKind.LOCAL, Confidence.CONFIRMED
        return specifier, DependencyKind.EXTERNAL, Confidence.HEURISTIC
    return _external_package(specifier), DependencyKind.EXTERNAL, Confidence.HEURISTIC


def _first_error(node: Node) -> Node | None:
    pending = [node]
    while pending:
        current = pending.pop()
        if current.is_error or current.is_missing:
            return current
        pending.extend(reversed(current.children))
    return None


def _is_async(source: bytes, node: Node) -> bool:
    return any(child.type == "async" for child in node.children) or _node_text(
        source, node
    ).lstrip().startswith("async ")


def _is_conventional_entry(path: str) -> bool:
    relative = PurePosixPath(path)
    parts = list(relative.parts)
    source_roots = [index for index, part in enumerate(parts[:-1]) if part == "src"]
    if source_roots:
        parts = parts[source_roots[-1] + 1 :]
    return len(parts) == 1 and _script_stem(PurePosixPath(parts[0])) in {
        "index",
        "main",
        "server",
    }


def _is_commonjs_main_guard(source: bytes, node: Node) -> bool:
    condition = node.child_by_field_name("condition")
    compact = "".join(_node_text(source, condition).split()).strip("()")
    return compact in {"require.main===module", "module===require.main"}


class TypeScriptRepositoryAnalyzer:
    """Parse script source without importing, bundling, or executing it."""

    def __init__(self, limits: ScriptAnalysisLimits | None = None) -> None:
        self.limits = limits or ScriptAnalysisLimits()
        self._typescript_parser = Parser(Language(tree_sitter_typescript.language_typescript()))
        self._tsx_parser = Parser(Language(tree_sitter_typescript.language_tsx()))

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
                if (
                    source_path.suffix.casefold() not in _LANGUAGE_BY_EXTENSION
                    or source_path.is_symlink()
                ):
                    continue

                relative = PurePosixPath(source_path.relative_to(root).as_posix())
                if len(relative.parts) > self.limits.max_path_depth:
                    raise RepositoryAnalysisError(
                        "analysis_limit_exceeded",
                        "A script source path is deeper than the supported analysis limit.",
                    )
                if len(relative.as_posix()) > self.limits.max_path_length:
                    raise RepositoryAnalysisError(
                        "analysis_limit_exceeded",
                        "A script source path is longer than the supported analysis limit.",
                    )
                try:
                    source_bytes = source_path.stat().st_size
                except OSError as exc:
                    raise RepositoryAnalysisError(
                        "source_read_failed", "A script source file could not be inspected."
                    ) from exc
                if source_bytes > self.limits.max_single_source_bytes:
                    raise RepositoryAnalysisError(
                        "analysis_limit_exceeded",
                        "A script source file is beyond the supported analysis limit.",
                    )

                discovered.append(source_path)
                total_bytes += source_bytes
                if len(discovered) > self.limits.max_script_files:
                    raise RepositoryAnalysisError(
                        "analysis_limit_exceeded",
                        "The repository contains more script files than can be analyzed.",
                    )
                if total_bytes > self.limits.max_total_source_bytes:
                    raise RepositoryAnalysisError(
                        "analysis_limit_exceeded",
                        "The repository contains more script source than can be analyzed.",
                    )

        return tuple(discovered)

    @staticmethod
    def _read_source(path: Path) -> tuple[bytes, int, int]:
        try:
            content = path.read_bytes()
            decoded = content.decode("utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise RepositoryAnalysisError(
                "source_decode_failed", "A script source file could not be decoded."
            ) from exc
        return decoded.encode("utf-8"), len(content), len(decoded.splitlines())

    def _parser_for(self, language: str) -> Parser:
        return self._tsx_parser if language in {"tsx", "jsx"} else self._typescript_parser

    @staticmethod
    def _declaration_symbols(
        module_name: str,
        path: str,
        source: bytes,
        declaration: Node,
        decorators: tuple[str, ...],
    ) -> tuple[Symbol, ...]:
        symbols: list[Symbol] = []
        if declaration.type in _VARIABLE_DECLARATION_TYPES:
            for declarator in declaration.named_children:
                if declarator.type != "variable_declarator":
                    continue
                name_node = declarator.child_by_field_name("name")
                if name_node is None or name_node.type not in {"identifier", "type_identifier"}:
                    continue
                name = _node_text(source, name_node)
                value = declarator.child_by_field_name("value")
                if value is not None and value.type in {
                    "arrow_function",
                    "function_expression",
                    "generator_function",
                }:
                    kind = (
                        SymbolKind.ASYNC_FUNCTION
                        if _is_async(source, value)
                        else SymbolKind.FUNCTION
                    )
                else:
                    kind = SymbolKind.VARIABLE
                symbols.append(
                    Symbol(
                        name=name,
                        qualified_name=f"{module_name}.{name}",
                        kind=kind,
                        location=_source_location(path, declarator),
                        decorators=decorators,
                    )
                )
            return tuple(symbols)

        kind = _DECLARATION_TYPES.get(declaration.type)
        if kind is None:
            return ()
        name_node = declaration.child_by_field_name("name")
        if name_node is None:
            return ()
        name = _node_text(source, name_node)
        if kind is SymbolKind.FUNCTION and _is_async(source, declaration):
            kind = SymbolKind.ASYNC_FUNCTION
        return (
            Symbol(
                name=name,
                qualified_name=f"{module_name}.{name}",
                kind=kind,
                location=_source_location(path, declaration),
                decorators=decorators,
            ),
        )

    def _symbols(
        self, module_name: str, path: str, source: bytes, root_node: Node
    ) -> tuple[Symbol, ...]:
        symbols: list[Symbol] = []
        for top_level in root_node.named_children:
            declaration = top_level
            decorator_nodes: list[Node] = []
            if top_level.type == "export_statement":
                declaration = top_level.child_by_field_name("declaration")
                decorator_nodes.extend(
                    child for child in top_level.named_children if child.type == "decorator"
                )
                if declaration is None:
                    continue
            if declaration.type == "ambient_declaration":
                declaration = next(
                    (child for child in declaration.named_children if child.type != "decorator"),
                    None,
                )
                if declaration is None:
                    continue
            decorator_nodes.extend(
                child for child in declaration.named_children if child.type == "decorator"
            )
            decorators = tuple(
                name
                for decorator in decorator_nodes
                if (name := _decorator_name(source, decorator)) is not None
            )
            symbols.extend(
                self._declaration_symbols(
                    module_name,
                    path,
                    source,
                    declaration,
                    decorators,
                )
            )
        return tuple(symbols)

    def _parse_modules(
        self, root: Path, paths: tuple[Path, ...]
    ) -> tuple[tuple[_ParsedScriptModule, ...], tuple[AnalysisDiagnostic, ...]]:
        parsed: list[_ParsedScriptModule] = []
        diagnostics: list[AnalysisDiagnostic] = []

        for source_path in paths:
            relative = PurePosixPath(source_path.relative_to(root).as_posix())
            relative_text = relative.as_posix()
            language = _LANGUAGE_BY_EXTENSION[source_path.suffix.casefold()]
            try:
                source, source_bytes, line_count = self._read_source(source_path)
            except RepositoryAnalysisError as exc:
                diagnostics.append(
                    AnalysisDiagnostic(code=exc.code, message=exc.message, path=relative_text)
                )
                continue

            tree = self._parser_for(language).parse(source)
            if tree.root_node.has_error:
                error = _first_error(tree.root_node)
                diagnostics.append(
                    AnalysisDiagnostic(
                        code="script_syntax_error",
                        message="TypeScript or JavaScript syntax could not be parsed.",
                        path=relative_text,
                        line=error.start_point.row + 1 if error is not None else None,
                    )
                )
                continue

            module_name = _module_name(relative)
            parsed.append(
                _ParsedScriptModule(
                    module=ScriptModule(
                        name=module_name,
                        path=relative_text,
                        language=language,
                        source_bytes=source_bytes,
                        line_count=line_count,
                        symbols=self._symbols(
                            module_name,
                            relative_text,
                            source,
                            tree.root_node,
                        ),
                    ),
                    tree=tree,
                    source=source,
                )
            )

        module_counts = Counter(item.module.name for item in parsed)
        ambiguous_names = {module_name for module_name, count in module_counts.items() if count > 1}
        if ambiguous_names:
            unambiguous: list[_ParsedScriptModule] = []
            for item in parsed:
                if item.module.name in ambiguous_names:
                    diagnostics.append(
                        AnalysisDiagnostic(
                            code="script_module_ambiguous",
                            message="Multiple script files resolve to the same module name.",
                            path=item.module.path,
                        )
                    )
                else:
                    unambiguous.append(item)
            parsed = unambiguous

        return tuple(parsed), tuple(diagnostics)

    @staticmethod
    def _local_module_map(
        modules: tuple[_ParsedScriptModule, ...],
    ) -> dict[str, str]:
        local: dict[str, str] = {}
        for parsed in modules:
            for key in _module_lookup_keys(parsed.module.path):
                local[key] = parsed.module.name
        return local

    @staticmethod
    def _dependency_specifier(parsed: _ParsedScriptModule, node: Node) -> str | None:
        source_node: Node | None = None
        if node.type in {"import_statement", "export_statement"}:
            source_node = node.child_by_field_name("source")
        elif node.type == "call_expression":
            function = node.child_by_field_name("function")
            if _node_text(parsed.source, function) not in {"import", "require"}:
                return None
            arguments = node.child_by_field_name("arguments")
            if arguments is not None and arguments.named_child_count == 1:
                candidate = arguments.named_children[0]
                if candidate.type == "string":
                    source_node = candidate
        return _string_value(parsed.source, source_node)

    @classmethod
    def _dependencies(cls, modules: tuple[_ParsedScriptModule, ...]) -> tuple[Dependency, ...]:
        local_modules = cls._local_module_map(modules)
        dependencies: list[Dependency] = []
        seen: set[tuple[str, str, DependencyKind]] = set()

        for parsed in modules:
            for node in _walk_named(parsed.tree.root_node):
                specifier = cls._dependency_specifier(parsed, node)
                if specifier is None:
                    continue
                target, kind, confidence = _resolve_dependency(
                    parsed.module.path,
                    specifier,
                    local_modules,
                )
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
                        location=_source_location(parsed.module.path, node),
                    )
                )

        return tuple(
            sorted(
                dependencies,
                key=lambda item: (item.source, item.target, item.location.line, item.kind),
            )
        )

    @staticmethod
    def _entry_points(
        modules: tuple[_ParsedScriptModule, ...],
    ) -> tuple[EntryPoint, ...]:
        entries: list[EntryPoint] = []
        for parsed in modules:
            guard: Node | None = None
            for node in _walk_named(parsed.tree.root_node):
                if node.type == "if_statement" and _is_commonjs_main_guard(parsed.source, node):
                    guard = node
                    break

            if guard is not None:
                entries.append(
                    EntryPoint(
                        module=parsed.module.name,
                        kind="commonjs_main_guard",
                        confidence=Confidence.CONFIRMED,
                        location=_source_location(parsed.module.path, guard),
                    )
                )
                continue

            if _is_conventional_entry(parsed.module.path):
                entries.append(
                    EntryPoint(
                        module=parsed.module.name,
                        kind="conventional_entry_file",
                        confidence=Confidence.HEURISTIC,
                        location=SourceLocation(
                            path=parsed.module.path,
                            line=1,
                            end_line=1,
                        ),
                    )
                )
                continue

            main_symbol = next(
                (symbol for symbol in parsed.module.symbols if symbol.name == "main"),
                None,
            )
            if main_symbol is not None:
                entries.append(
                    EntryPoint(
                        module=parsed.module.name,
                        kind="main_function",
                        confidence=Confidence.HEURISTIC,
                        location=main_symbol.location,
                    )
                )

        return tuple(sorted(entries, key=lambda item: (item.module, item.location.line, item.kind)))

    def analyze(self, repository_root: Path) -> ScriptAnalysisArtifact:
        """Return a deterministic script artifact for an extracted repository."""

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
        return ScriptAnalysisArtifact(
            schema_version="1.0",
            language="typescript-javascript",
            modules=modules,
            dependencies=dependencies,
            entry_points=entry_points,
            diagnostics=tuple(sorted(diagnostics, key=lambda item: item.path)),
            summary=AnalysisSummary(
                module_count=len(modules),
                symbol_count=sum(len(module.symbols) for module in modules),
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
