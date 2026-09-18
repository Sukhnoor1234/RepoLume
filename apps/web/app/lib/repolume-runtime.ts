const API_URL_ENVIRONMENT_VARIABLE = "REPOLUME_API_URL";

export function analysisApiBaseUrl(): URL | null {
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

export function isLiveAnalysisEnabled(): boolean {
  return analysisApiBaseUrl() !== null;
}
