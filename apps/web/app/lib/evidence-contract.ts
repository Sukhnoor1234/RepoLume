import type { ArchitectureNodeKind, SourceLocation } from "@/app/lib/architecture-contract";

export type EvidenceMatch = {
  nodeId: string;
  kind: Extract<ArchitectureNodeKind, "module" | "symbol" | "entry_point">;
  name: string;
  language: string | null;
  location: SourceLocation;
  confidence: "confirmed" | "heuristic";
  score: number;
  matchedTerms: string[];
  relationshipCount: number;
};

export type EvidenceQueryResult = {
  schemaVersion: "1.0";
  question: string;
  matches: EvidenceMatch[];
};

const EVIDENCE_KINDS = new Set(["module", "symbol", "entry_point"]);
const CONFIDENCE_LEVELS = new Set(["confirmed", "heuristic"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function parseMatch(value: unknown): EvidenceMatch | null {
  if (!isRecord(value) || !isRecord(value.location)) return null;
  if (
    typeof value.node_id !== "string" ||
    !value.node_id ||
    typeof value.kind !== "string" ||
    !EVIDENCE_KINDS.has(value.kind) ||
    typeof value.name !== "string" ||
    !value.name ||
    !(value.language === null || typeof value.language === "string") ||
    typeof value.confidence !== "string" ||
    !CONFIDENCE_LEVELS.has(value.confidence) ||
    !isPositiveInteger(value.score) ||
    !Array.isArray(value.matched_terms) ||
    !value.matched_terms.every((term) => typeof term === "string" && term.length > 0) ||
    !isNonNegativeInteger(value.relationship_count) ||
    typeof value.location.path !== "string" ||
    !value.location.path ||
    !isPositiveInteger(value.location.line) ||
    !isPositiveInteger(value.location.end_line) ||
    value.location.end_line < value.location.line
  ) {
    return null;
  }
  return {
    nodeId: value.node_id,
    kind: value.kind as EvidenceMatch["kind"],
    name: value.name,
    language: value.language,
    location: {
      path: value.location.path,
      line: value.location.line,
      endLine: value.location.end_line,
    },
    confidence: value.confidence as EvidenceMatch["confidence"],
    score: value.score,
    matchedTerms: [...value.matched_terms],
    relationshipCount: value.relationship_count,
  };
}

export function parseEvidenceQueryResult(value: unknown): EvidenceQueryResult | null {
  if (
    !isRecord(value) ||
    value.schema_version !== "1.0" ||
    typeof value.question !== "string" ||
    !Array.isArray(value.matches)
  ) {
    return null;
  }
  const matches = value.matches.map(parseMatch);
  if (matches.some((match) => match === null)) return null;
  return {
    schemaVersion: "1.0",
    question: value.question,
    matches: matches as EvidenceMatch[],
  };
}
