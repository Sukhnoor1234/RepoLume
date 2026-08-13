import { invalidRequest, proxyApiRequest } from "@/app/lib/repolume-api";

const ANALYSIS_ID = /^[A-Za-z0-9_-]{1,64}$/;

type RouteContext = {
  params: Promise<{ analysisId: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  const { analysisId } = await context.params;
  if (!ANALYSIS_ID.test(analysisId)) {
    return invalidRequest("The analysis identifier is invalid.");
  }
  return proxyApiRequest(`/v1/analyses/${encodeURIComponent(analysisId)}`);
}
