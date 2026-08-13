const ANALYSIS_ID = /^[A-Za-z0-9_-]{1,64}$/;

export function isAnalysisId(value: string): boolean {
  return ANALYSIS_ID.test(value);
}
