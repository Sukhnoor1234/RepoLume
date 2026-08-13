import { invalidRequest, proxyApiRequest } from "@/app/lib/repolume-api";

type AnalysisSubmission = {
  repository_url: string;
  ref?: string | null;
};

function isSubmission(value: unknown): value is AnalysisSubmission {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  const keys = Object.keys(candidate);
  return (
    keys.every((key) => key === "repository_url" || key === "ref") &&
    typeof candidate.repository_url === "string" &&
    candidate.repository_url.length > 0 &&
    candidate.repository_url.length <= 2048 &&
    (candidate.ref === undefined ||
      candidate.ref === null ||
      (typeof candidate.ref === "string" && candidate.ref.length > 0 && candidate.ref.length <= 255))
  );
}

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return invalidRequest("Enter a valid public GitHub repository URL.");
  }

  if (!isSubmission(payload)) {
    return invalidRequest("Enter a valid public GitHub repository URL.");
  }
  return proxyApiRequest("/v1/analyses", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
