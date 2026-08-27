import { isAnalysisId } from "@/app/lib/analysis-id";
import { invalidRequest, proxyApiRequest } from "@/app/lib/repolume-api";

type RouteContext = {
  params: Promise<{ analysisId: string }>;
};

type EvidenceQuery = {
  question: string;
  limit?: number;
};

function isEvidenceQuery(value: unknown): value is EvidenceQuery {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  return (
    Object.keys(candidate).every((key) => key === "question" || key === "limit") &&
    typeof candidate.question === "string" &&
    candidate.question.trim().length >= 3 &&
    candidate.question.length <= 300 &&
    (candidate.limit === undefined ||
      (typeof candidate.limit === "number" &&
        Number.isInteger(candidate.limit) &&
        candidate.limit >= 1 &&
        candidate.limit <= 10))
  );
}

export async function POST(request: Request, context: RouteContext) {
  const { analysisId } = await context.params;
  if (!isAnalysisId(analysisId)) {
    return invalidRequest("The analysis identifier is invalid.");
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return invalidRequest("Ask a question between 3 and 300 characters.");
  }
  if (!isEvidenceQuery(payload)) {
    return invalidRequest("Ask a question between 3 and 300 characters.");
  }

  return proxyApiRequest(
    `/v1/analyses/${encodeURIComponent(analysisId)}/evidence-query`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}
