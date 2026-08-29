import { isAnalysisId } from "@/app/lib/analysis-id";
import { invalidRequest, proxyApiRequest } from "@/app/lib/repolume-api";
import { isRepositoryQuestion } from "@/app/lib/repository-question";

type RouteContext = {
  params: Promise<{ analysisId: string }>;
};

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
  if (!isRepositoryQuestion(payload)) {
    return invalidRequest("Ask a question between 3 and 300 characters.");
  }

  return proxyApiRequest(
    `/v1/analyses/${encodeURIComponent(analysisId)}/answer`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}
