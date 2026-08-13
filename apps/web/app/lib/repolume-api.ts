import { NextResponse } from "next/server";

const API_URL_ENVIRONMENT_VARIABLE = "REPOLUME_API_URL";
const MAXIMUM_RESPONSE_BYTES = 1_000_000;

type ErrorEnvelope = {
  error: {
    code: string;
    message: string;
  };
};

function errorResponse(status: number, code: string, message: string) {
  return NextResponse.json<ErrorEnvelope>(
    { error: { code, message } },
    { status, headers: { "cache-control": "no-store" } },
  );
}

function apiBaseUrl(): URL | null {
  const configuredUrl = process.env[API_URL_ENVIRONMENT_VARIABLE];
  if (!configuredUrl) return null;

  try {
    const url = new URL(configuredUrl);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash
    ) {
      return null;
    }
    return url;
  } catch {
    return null;
  }
}

export async function proxyApiRequest(path: string, init?: RequestInit) {
  const baseUrl = apiBaseUrl();
  if (!baseUrl) {
    return errorResponse(
      503,
      "analysis_service_unavailable",
      "Repository analysis is temporarily unavailable.",
    );
  }

  let response: Response;
  try {
    response = await fetch(new URL(path, baseUrl), {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
      headers: {
        accept: "application/json",
        ...(init?.body ? { "content-type": "application/json" } : {}),
      },
    });
  } catch {
    return errorResponse(
      503,
      "analysis_service_unavailable",
      "Repository analysis is temporarily unavailable.",
    );
  }

  const contentLength = Number(response.headers.get("content-length") ?? 0);
  if (contentLength > MAXIMUM_RESPONSE_BYTES) {
    return errorResponse(502, "analysis_response_invalid", "The analysis service returned an invalid response.");
  }

  try {
    const text = await response.text();
    if (new TextEncoder().encode(text).byteLength > MAXIMUM_RESPONSE_BYTES) {
      return errorResponse(502, "analysis_response_invalid", "The analysis service returned an invalid response.");
    }
    const payload: unknown = JSON.parse(text);
    if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
      throw new TypeError("Expected a JSON object");
    }
    return NextResponse.json(payload, {
      status: response.status,
      headers: { "cache-control": "no-store" },
    });
  } catch {
    return errorResponse(502, "analysis_response_invalid", "The analysis service returned an invalid response.");
  }
}

export function invalidRequest(message: string) {
  return errorResponse(400, "validation_error", message);
}
