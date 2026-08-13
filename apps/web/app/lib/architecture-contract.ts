export type SourceLocation = {
  path: string;
  line: number;
  endLine: number;
};

export type ArchitectureNodeKind =
  | "repository"
  | "module"
  | "symbol"
  | "entry_point"
  | "external_dependency";

export type ArchitectureNode = {
  id: string;
  kind: ArchitectureNodeKind;
  name: string;
  language: string | null;
  location: SourceLocation | null;
  qualifiedName: string | null;
  symbolKind:
    | "function"
    | "async_function"
    | "class"
    | "variable"
    | "interface"
    | "type_alias"
    | "enum"
    | null;
  detail: string | null;
  confidence: "confirmed" | "heuristic" | null;
  decorators: string[];
  sourceBytes: number | null;
  lineCount: number | null;
};

export type ArchitectureEdge = {
  id: string;
  kind: "contains" | "depends_on";
  source: string;
  target: string;
  confidence: "confirmed" | "heuristic";
  location: SourceLocation;
};

export type ArchitectureSummary = {
  languageCount: number;
  nodeCount: number;
  edgeCount: number;
  moduleCount: number;
  symbolCount: number;
  entryPointCount: number;
  externalDependencyCount: number;
  dependencyCount: number;
  diagnosticCount: number;
};

export type ArchitectureDiagnostic = {
  language: string;
  code: string;
  message: string;
  path: string;
  line: number | null;
};

export type RepositoryArchitecture = {
  schemaVersion: "1.0";
  languages: string[];
  nodes: ArchitectureNode[];
  edges: ArchitectureEdge[];
  diagnostics: ArchitectureDiagnostic[];
  summary: ArchitectureSummary;
};

const NODE_KINDS = new Set<ArchitectureNodeKind>([
  "repository",
  "module",
  "symbol",
  "entry_point",
  "external_dependency",
]);
const EDGE_KINDS = new Set(["contains", "depends_on"] as const);
const CONFIDENCE = new Set(["confirmed", "heuristic"] as const);
const SYMBOL_KINDS = new Set([
  "function",
  "async_function",
  "class",
  "variable",
  "interface",
  "type_alias",
  "enum",
] as const);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function positiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function parseLocation(value: unknown): SourceLocation | null | undefined {
  if (value === null) return null;
  if (
    !isRecord(value) ||
    typeof value.path !== "string" ||
    !value.path ||
    !positiveInteger(value.line) ||
    !positiveInteger(value.end_line) ||
    value.end_line < value.line
  ) {
    return undefined;
  }
  return { path: value.path, line: value.line, endLine: value.end_line };
}

function parseNode(value: unknown): ArchitectureNode | null {
  if (!isRecord(value)) return null;
  const location = parseLocation(value.location);
  if (
    typeof value.id !== "string" ||
    !value.id ||
    typeof value.kind !== "string" ||
    !NODE_KINDS.has(value.kind as ArchitectureNodeKind) ||
    typeof value.name !== "string" ||
    !value.name ||
    !(value.language === null || typeof value.language === "string") ||
    location === undefined ||
    !(value.qualified_name === null || typeof value.qualified_name === "string") ||
    !(
      value.symbol_kind === null ||
      (typeof value.symbol_kind === "string" &&
        SYMBOL_KINDS.has(value.symbol_kind as ArchitectureNode["symbolKind"] & string))
    ) ||
    !(value.detail === null || typeof value.detail === "string") ||
    !(
      value.confidence === null ||
      (typeof value.confidence === "string" &&
        CONFIDENCE.has(value.confidence as "confirmed" | "heuristic"))
    ) ||
    !Array.isArray(value.decorators) ||
    !value.decorators.every((decorator) => typeof decorator === "string") ||
    !(value.source_bytes === null || nonNegativeInteger(value.source_bytes)) ||
    !(value.line_count === null || nonNegativeInteger(value.line_count))
  ) {
    return null;
  }
  return {
    id: value.id,
    kind: value.kind as ArchitectureNodeKind,
    name: value.name,
    language: value.language,
    location,
    qualifiedName: value.qualified_name,
    symbolKind: value.symbol_kind as ArchitectureNode["symbolKind"],
    detail: value.detail,
    confidence: value.confidence as ArchitectureNode["confidence"],
    decorators: [...value.decorators],
    sourceBytes: value.source_bytes,
    lineCount: value.line_count,
  };
}

function parseDiagnostic(value: unknown): ArchitectureDiagnostic | null {
  if (
    !isRecord(value) ||
    typeof value.language !== "string" ||
    !value.language ||
    typeof value.code !== "string" ||
    !value.code ||
    typeof value.message !== "string" ||
    typeof value.path !== "string" ||
    !value.path ||
    !(value.line === null || positiveInteger(value.line))
  ) {
    return null;
  }
  return {
    language: value.language,
    code: value.code,
    message: value.message,
    path: value.path,
    line: value.line,
  };
}

function parseEdge(value: unknown): ArchitectureEdge | null {
  if (!isRecord(value)) return null;
  const location = parseLocation(value.location);
  if (
    typeof value.id !== "string" ||
    !value.id ||
    typeof value.kind !== "string" ||
    !EDGE_KINDS.has(value.kind as "contains" | "depends_on") ||
    typeof value.source !== "string" ||
    typeof value.target !== "string" ||
    typeof value.confidence !== "string" ||
    !CONFIDENCE.has(value.confidence as "confirmed" | "heuristic") ||
    !location
  ) {
    return null;
  }
  return {
    id: value.id,
    kind: value.kind as ArchitectureEdge["kind"],
    source: value.source,
    target: value.target,
    confidence: value.confidence as ArchitectureEdge["confidence"],
    location,
  };
}

function parseSummary(value: unknown): ArchitectureSummary | null {
  if (!isRecord(value)) return null;
  const keys = [
    "language_count",
    "node_count",
    "edge_count",
    "module_count",
    "symbol_count",
    "entry_point_count",
    "external_dependency_count",
    "dependency_count",
    "diagnostic_count",
  ] as const;
  if (!keys.every((key) => nonNegativeInteger(value[key]))) return null;
  return {
    languageCount: value.language_count as number,
    nodeCount: value.node_count as number,
    edgeCount: value.edge_count as number,
    moduleCount: value.module_count as number,
    symbolCount: value.symbol_count as number,
    entryPointCount: value.entry_point_count as number,
    externalDependencyCount: value.external_dependency_count as number,
    dependencyCount: value.dependency_count as number,
    diagnosticCount: value.diagnostic_count as number,
  };
}

export function parseArchitecture(value: unknown): RepositoryArchitecture | null {
  if (
    !isRecord(value) ||
    value.schema_version !== "1.0" ||
    !Array.isArray(value.languages) ||
    !value.languages.every((language) => typeof language === "string" && language.length > 0) ||
    !Array.isArray(value.nodes) ||
    !Array.isArray(value.edges) ||
    !Array.isArray(value.diagnostics)
  ) {
    return null;
  }
  const nodes = value.nodes.map(parseNode);
  const edges = value.edges.map(parseEdge);
  const diagnostics = value.diagnostics.map(parseDiagnostic);
  const summary = parseSummary(value.summary);
  if (
    nodes.some((node) => node === null) ||
    edges.some((edge) => edge === null) ||
    diagnostics.some((diagnostic) => diagnostic === null) ||
    !summary
  ) {
    return null;
  }
  const parsedNodes = nodes as ArchitectureNode[];
  const parsedEdges = edges as ArchitectureEdge[];
  const parsedDiagnostics = diagnostics as ArchitectureDiagnostic[];
  const nodeIds = new Set(parsedNodes.map((node) => node.id));
  if (
    new Set(value.languages).size !== value.languages.length ||
    nodeIds.size !== parsedNodes.length ||
    new Set(parsedEdges.map((edge) => edge.id)).size !== parsedEdges.length ||
    parsedEdges.some((edge) => !nodeIds.has(edge.source) || !nodeIds.has(edge.target)) ||
    summary.nodeCount !== parsedNodes.length ||
    summary.edgeCount !== parsedEdges.length ||
    summary.languageCount !== value.languages.length ||
    summary.moduleCount !== parsedNodes.filter((node) => node.kind === "module").length ||
    summary.symbolCount !== parsedNodes.filter((node) => node.kind === "symbol").length ||
    summary.entryPointCount !==
      parsedNodes.filter((node) => node.kind === "entry_point").length ||
    summary.externalDependencyCount !==
      parsedNodes.filter((node) => node.kind === "external_dependency").length ||
    summary.dependencyCount !== parsedEdges.filter((edge) => edge.kind === "depends_on").length ||
    summary.diagnosticCount !== parsedDiagnostics.length
  ) {
    return null;
  }
  return {
    schemaVersion: "1.0",
    languages: [...value.languages],
    nodes: parsedNodes,
    edges: parsedEdges,
    diagnostics: parsedDiagnostics,
    summary,
  };
}
