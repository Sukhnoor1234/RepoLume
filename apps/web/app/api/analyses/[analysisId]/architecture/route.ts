import { isAnalysisId } from "@/app/lib/analysis-id";
import { invalidRequest, proxyApiRequest } from "@/app/lib/repolume-api";

type RouteContext = {
  params: Promise<{ analysisId: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  const { analysisId } = await context.params;
  if (!isAnalysisId(analysisId)) {
    return invalidRequest("The analysis identifier is invalid.");
  }
  return proxyApiRequest(`/v1/analyses/${encodeURIComponent(analysisId)}/architecture`);
}
