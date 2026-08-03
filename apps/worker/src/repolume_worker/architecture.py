"""Compose language-specific analysis into one deterministic architecture graph."""

from collections.abc import Iterable
from urllib.parse import quote

from repolume_worker.analysis_models import (
    Confidence,
    DependencyKind,
    PythonAnalysisArtifact,
    PythonModule,
    ScriptAnalysisArtifact,
    ScriptModule,
    SourceLocation,
)
from repolume_worker.architecture_models import (
    ArchitectureDiagnostic,
    ArchitectureEdge,
    ArchitectureEdgeKind,
    ArchitectureNode,
    ArchitectureNodeKind,
    ArchitectureSummary,
    RepositoryArchitectureArtifact,
)

_ANALYSIS_SCHEMA_VERSION = "1.0"
_ARCHITECTURE_SCHEMA_VERSION = "1.0"
_REPOSITORY_NODE_ID = "repository"


def _stable_id(prefix: str, *parts: object) -> str:
    encoded = (quote(str(part), safe="") for part in parts)
    return ":".join((prefix, *encoded))


def _module_id(analysis_language: str, path: str) -> str:
    return _stable_id("module", analysis_language, path)


def _symbol_id(analysis_language: str, path: str, line: int, name: str) -> str:
    return _stable_id("symbol", analysis_language, path, line, name)


def _entry_id(analysis_language: str, path: str, line: int, kind: str) -> str:
    return _stable_id("entry", analysis_language, path, line, kind)


def _external_id(analysis_language: str, target: str) -> str:
    return _stable_id("external", analysis_language, target)


def _edge_id(kind: ArchitectureEdgeKind, source: str, target: str) -> str:
    return _stable_id("edge", kind, source, target)


class RepositoryArchitectureComposer:
    """Merge source artifacts without inventing cross-language relationships."""

    @staticmethod
    def _module_node(
        analysis_language: str,
        module: PythonModule | ScriptModule,
    ) -> ArchitectureNode:
        language = module.language if isinstance(module, ScriptModule) else "python"
        return ArchitectureNode(
            id=_module_id(analysis_language, module.path),
            kind=ArchitectureNodeKind.MODULE,
            name=module.name,
            language=language,
            location=SourceLocation(path=module.path, line=1, end_line=1),
            qualified_name=module.name,
            confidence=Confidence.CONFIRMED,
            source_bytes=module.source_bytes,
            line_count=module.line_count,
        )

    @staticmethod
    def _contains_edge(
        source: str,
        target: str,
        location: SourceLocation,
        confidence: Confidence,
    ) -> ArchitectureEdge:
        return ArchitectureEdge(
            id=_edge_id(ArchitectureEdgeKind.CONTAINS, source, target),
            kind=ArchitectureEdgeKind.CONTAINS,
            source=source,
            target=target,
            confidence=confidence,
            location=location,
        )

    def compose(
        self,
        artifacts: Iterable[PythonAnalysisArtifact | ScriptAnalysisArtifact],
    ) -> RepositoryArchitectureArtifact:
        """Return one stable graph for the supplied language artifacts."""

        ordered = tuple(sorted(artifacts, key=lambda artifact: artifact.language))
        artifact_languages = tuple(artifact.language for artifact in ordered)
        languages = tuple(
            artifact.language for artifact in ordered if artifact.modules or artifact.diagnostics
        )
        if len(artifact_languages) != len(set(artifact_languages)):
            raise ValueError("Only one artifact per analysis language can be composed.")
        if any(artifact.schema_version != _ANALYSIS_SCHEMA_VERSION for artifact in ordered):
            raise ValueError("An analysis artifact uses an unsupported schema version.")

        nodes: dict[str, ArchitectureNode] = {
            _REPOSITORY_NODE_ID: ArchitectureNode(
                id=_REPOSITORY_NODE_ID,
                kind=ArchitectureNodeKind.REPOSITORY,
                name="Repository",
                language=None,
                confidence=Confidence.CONFIRMED,
            )
        }
        edges: dict[str, ArchitectureEdge] = {}
        diagnostics: list[ArchitectureDiagnostic] = []

        for artifact in ordered:
            module_ids = {
                module.name: _module_id(artifact.language, module.path)
                for module in artifact.modules
            }

            for module in artifact.modules:
                module_node = self._module_node(artifact.language, module)
                nodes[module_node.id] = module_node
                module_location = module_node.location
                if module_location is None:
                    raise ValueError("A module node must include source evidence.")
                contains_module = self._contains_edge(
                    _REPOSITORY_NODE_ID,
                    module_node.id,
                    module_location,
                    Confidence.CONFIRMED,
                )
                edges[contains_module.id] = contains_module

                for symbol in module.symbols:
                    symbol_node = ArchitectureNode(
                        id=_symbol_id(
                            artifact.language,
                            symbol.location.path,
                            symbol.location.line,
                            symbol.name,
                        ),
                        kind=ArchitectureNodeKind.SYMBOL,
                        name=symbol.name,
                        language=module_node.language,
                        location=symbol.location,
                        qualified_name=symbol.qualified_name,
                        symbol_kind=symbol.kind,
                        confidence=Confidence.CONFIRMED,
                        decorators=symbol.decorators,
                    )
                    nodes[symbol_node.id] = symbol_node
                    contains_symbol = self._contains_edge(
                        module_node.id,
                        symbol_node.id,
                        symbol.location,
                        Confidence.CONFIRMED,
                    )
                    edges[contains_symbol.id] = contains_symbol

            for dependency in artifact.dependencies:
                source_id = module_ids.get(dependency.source)
                if source_id is None:
                    raise ValueError("A dependency source module is missing from its artifact.")

                if dependency.kind is DependencyKind.LOCAL:
                    target_id = module_ids.get(dependency.target)
                    if target_id is None:
                        raise ValueError("A local dependency target is missing from its artifact.")
                else:
                    target_id = _external_id(artifact.language, dependency.target)
                    nodes.setdefault(
                        target_id,
                        ArchitectureNode(
                            id=target_id,
                            kind=ArchitectureNodeKind.EXTERNAL_DEPENDENCY,
                            name=dependency.target,
                            language=artifact.language,
                            confidence=dependency.confidence,
                        ),
                    )

                dependency_edge = ArchitectureEdge(
                    id=_edge_id(ArchitectureEdgeKind.DEPENDS_ON, source_id, target_id),
                    kind=ArchitectureEdgeKind.DEPENDS_ON,
                    source=source_id,
                    target=target_id,
                    confidence=dependency.confidence,
                    location=dependency.location,
                )
                edges[dependency_edge.id] = dependency_edge

            for entry in artifact.entry_points:
                module_id = module_ids.get(entry.module)
                if module_id is None:
                    raise ValueError("An entry point module is missing from its artifact.")
                module_node = nodes[module_id]
                entry_node = ArchitectureNode(
                    id=_entry_id(
                        artifact.language,
                        entry.location.path,
                        entry.location.line,
                        entry.kind,
                    ),
                    kind=ArchitectureNodeKind.ENTRY_POINT,
                    name=entry.kind,
                    language=module_node.language,
                    location=entry.location,
                    qualified_name=entry.module,
                    detail=entry.kind,
                    confidence=entry.confidence,
                )
                nodes[entry_node.id] = entry_node
                contains_entry = self._contains_edge(
                    module_id,
                    entry_node.id,
                    entry.location,
                    entry.confidence,
                )
                edges[contains_entry.id] = contains_entry

            diagnostics.extend(
                ArchitectureDiagnostic(
                    language=artifact.language,
                    code=diagnostic.code,
                    message=diagnostic.message,
                    path=diagnostic.path,
                    line=diagnostic.line,
                )
                for diagnostic in artifact.diagnostics
            )

        sorted_nodes = tuple(sorted(nodes.values(), key=lambda node: node.id))
        sorted_edges = tuple(sorted(edges.values(), key=lambda edge: edge.id))
        sorted_diagnostics = tuple(
            sorted(
                diagnostics,
                key=lambda diagnostic: (
                    diagnostic.language,
                    diagnostic.path,
                    diagnostic.line or 0,
                    diagnostic.code,
                ),
            )
        )
        return RepositoryArchitectureArtifact(
            schema_version=_ARCHITECTURE_SCHEMA_VERSION,
            languages=languages,
            nodes=sorted_nodes,
            edges=sorted_edges,
            diagnostics=sorted_diagnostics,
            summary=ArchitectureSummary(
                language_count=len(languages),
                node_count=len(sorted_nodes),
                edge_count=len(sorted_edges),
                module_count=sum(node.kind is ArchitectureNodeKind.MODULE for node in sorted_nodes),
                symbol_count=sum(node.kind is ArchitectureNodeKind.SYMBOL for node in sorted_nodes),
                entry_point_count=sum(
                    node.kind is ArchitectureNodeKind.ENTRY_POINT for node in sorted_nodes
                ),
                external_dependency_count=sum(
                    node.kind is ArchitectureNodeKind.EXTERNAL_DEPENDENCY for node in sorted_nodes
                ),
                dependency_count=sum(
                    edge.kind is ArchitectureEdgeKind.DEPENDS_ON for edge in sorted_edges
                ),
                diagnostic_count=len(sorted_diagnostics),
            ),
        )
