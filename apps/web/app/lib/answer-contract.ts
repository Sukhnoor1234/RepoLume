import { parseEvidenceMatch } from "@/app/lib/evidence-contract";
import type { EvidenceMatch } from "@/app/lib/evidence-contract";

export type RepositoryAnswerResult = {
  schemaVersion: "1.0";
  question: string;
  answer: string;
  groundingStatus: "supported" | "insufficient_evidence";
  citations: EvidenceMatch[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseRepositoryAnswer(value: unknown): RepositoryAnswerResult | null {
  if (
    !isRecord(value) ||
    value.schema_version !== "1.0" ||
    typeof value.question !== "string" ||
    typeof value.answer !== "string" ||
    !value.answer ||
    (value.grounding_status !== "supported" &&
      value.grounding_status !== "insufficient_evidence") ||
    !Array.isArray(value.citations)
  ) {
    return null;
  }
  const citations = value.citations.map(parseEvidenceMatch);
  if (citations.some((citation) => citation === null)) return null;
  if (value.grounding_status === "supported" && citations.length === 0) return null;
  if (value.grounding_status === "insufficient_evidence" && citations.length > 0) return null;
  return {
    schemaVersion: "1.0",
    question: value.question,
    answer: value.answer,
    groundingStatus: value.grounding_status,
    citations: citations as EvidenceMatch[],
  };
}
