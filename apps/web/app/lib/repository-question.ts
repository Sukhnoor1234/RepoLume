export type RepositoryQuestion = {
  question: string;
  limit?: number;
};

export function isRepositoryQuestion(value: unknown): value is RepositoryQuestion {
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
