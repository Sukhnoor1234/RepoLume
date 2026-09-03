import type { RepositoryQuestion } from "@/app/lib/repository-question";

type SampleCitation = {
  node_id: string;
  kind: "module" | "symbol" | "entry_point";
  name: string;
  language: string | null;
  location: { path: string; line: number; end_line: number };
  confidence: "confirmed" | "heuristic";
  score: number;
  matched_terms: string[];
  relationship_count: number;
};

export type SampleRepository = {
  analysisId: string;
  name: string;
  language: string;
  description: string;
  suggestedQuestion: string;
};

const COMMERCE_ORDER: SampleCitation = {
  node_id: "symbol:typescript:createOrder",
  kind: "symbol",
  name: "createOrder",
  language: "typescript",
  location: { path: "src/services/orders.ts", line: 24, end_line: 51 },
  confidence: "confirmed",
  score: 13,
  matched_terms: ["order", "create"],
  relationship_count: 2,
};

const COMMERCE_ROUTE: SampleCitation = {
  node_id: "entry:typescript:post-orders",
  kind: "entry_point",
  name: "POST /orders",
  language: "typescript",
  location: { path: "src/routes/orders.ts", line: 10, end_line: 19 },
  confidence: "confirmed",
  score: 10,
  matched_terms: ["order", "route"],
  relationship_count: 1,
};

const TASK_AUTH: SampleCitation = {
  node_id: "symbol:python:require_user",
  kind: "symbol",
  name: "require_user",
  language: "python",
  location: { path: "src/tasks/auth.py", line: 8, end_line: 29 },
  confidence: "confirmed",
  score: 12,
  matched_terms: ["auth", "user"],
  relationship_count: 2,
};

const TASK_ROUTE: SampleCitation = {
  node_id: "entry:python:get-tasks",
  kind: "entry_point",
  name: "GET /tasks",
  language: "python",
  location: { path: "src/tasks/routes.py", line: 17, end_line: 36 },
  confidence: "confirmed",
  score: 8,
  matched_terms: ["task", "route"],
  relationship_count: 1,
};

export const SAMPLE_REPOSITORIES: SampleRepository[] = [
  {
    analysisId: "sample_commerce_platform",
    name: "Commerce platform",
    language: "TypeScript",
    description: "A small store API with order routes, services, and a cache dependency.",
    suggestedQuestion: "How does an order get created?",
  },
  {
    analysisId: "sample_task_api",
    name: "Task API",
    language: "Python",
    description: "A FastAPI-style task service with auth checks and route handlers.",
    suggestedQuestion: "Where is user authentication checked?",
  },
];

const SAMPLE_BY_ID = new Map(SAMPLE_REPOSITORIES.map((sample) => [sample.analysisId, sample]));

function sampleNode(
  id: string,
  kind: string,
  name: string,
  language: string | null,
  location: SampleCitation["location"] | null,
  detail: string | null,
  symbolKind: string | null = null,
) {
  return {
    id,
    kind,
    name,
    language,
    location,
    qualified_name: name,
    symbol_kind: symbolKind,
    detail,
    confidence: "confirmed",
    decorators: [],
    source_bytes: null,
    line_count: location ? location.end_line - location.line + 1 : null,
  };
}

function edge(id: string, kind: "contains" | "depends_on", source: string, target: string, path: string) {
  return {
    id,
    kind,
    source,
    target,
    confidence: "confirmed",
    location: { path, line: 1, end_line: 1 },
  };
}

const SAMPLE_ARCHITECTURES = {
  sample_commerce_platform: {
    schema_version: "1.0",
    languages: ["typescript"],
    nodes: [
      sampleNode("repository", "repository", "Commerce platform", null, null, "Sample repository for the live demo."),
      sampleNode(
        "module:typescript:src/routes/orders.ts",
        "module",
        "orders route",
        "typescript",
        { path: "src/routes/orders.ts", line: 1, end_line: 38 },
        "Accepts order requests and passes work to the service layer.",
      ),
      sampleNode(
        "module:typescript:src/services/orders.ts",
        "module",
        "orders service",
        "typescript",
        { path: "src/services/orders.ts", line: 1, end_line: 88 },
        "Creates orders, reserves inventory, and writes order records.",
      ),
      sampleNode(COMMERCE_ROUTE.node_id, "entry_point", COMMERCE_ROUTE.name, "typescript", COMMERCE_ROUTE.location, "Order creation endpoint."),
      sampleNode(COMMERCE_ORDER.node_id, "symbol", COMMERCE_ORDER.name, "typescript", COMMERCE_ORDER.location, "Core order creation function.", "function"),
      sampleNode(
        "dependency:redis",
        "external_dependency",
        "Redis",
        null,
        { path: "src/services/orders.ts", line: 47, end_line: 47 },
        "Caches order status after creation.",
      ),
    ],
    edges: [
      edge("edge:repo:routes", "contains", "repository", "module:typescript:src/routes/orders.ts", "src/routes/orders.ts"),
      edge("edge:repo:services", "contains", "repository", "module:typescript:src/services/orders.ts", "src/services/orders.ts"),
      edge("edge:routes:entry", "contains", "module:typescript:src/routes/orders.ts", COMMERCE_ROUTE.node_id, "src/routes/orders.ts"),
      edge("edge:services:create", "contains", "module:typescript:src/services/orders.ts", COMMERCE_ORDER.node_id, "src/services/orders.ts"),
      edge("edge:route:service", "depends_on", COMMERCE_ROUTE.node_id, COMMERCE_ORDER.node_id, "src/routes/orders.ts"),
      edge("edge:service:redis", "depends_on", COMMERCE_ORDER.node_id, "dependency:redis", "src/services/orders.ts"),
    ],
    diagnostics: [],
    summary: {
      language_count: 1,
      node_count: 6,
      edge_count: 6,
      module_count: 2,
      symbol_count: 1,
      entry_point_count: 1,
      external_dependency_count: 1,
      dependency_count: 2,
      diagnostic_count: 0,
    },
  },
  sample_task_api: {
    schema_version: "1.0",
    languages: ["python"],
    nodes: [
      sampleNode("repository", "repository", "Task API", null, null, "Sample repository for the live demo."),
      sampleNode(
        "module:python:src/tasks/routes.py",
        "module",
        "tasks routes",
        "python",
        { path: "src/tasks/routes.py", line: 1, end_line: 70 },
        "Defines HTTP routes for reading and updating tasks.",
      ),
      sampleNode(
        "module:python:src/tasks/auth.py",
        "module",
        "auth helpers",
        "python",
        { path: "src/tasks/auth.py", line: 1, end_line: 44 },
        "Checks request users before task data is returned.",
      ),
      sampleNode(TASK_ROUTE.node_id, "entry_point", TASK_ROUTE.name, "python", TASK_ROUTE.location, "Lists tasks for the signed-in user."),
      sampleNode(TASK_AUTH.node_id, "symbol", TASK_AUTH.name, "python", TASK_AUTH.location, "Validates that a request has an active user.", "function"),
      sampleNode(
        "dependency:postgres",
        "external_dependency",
        "PostgreSQL",
        null,
        { path: "src/tasks/repository.py", line: 12, end_line: 12 },
        "Stores task records.",
      ),
    ],
    edges: [
      edge("edge:repo:routes", "contains", "repository", "module:python:src/tasks/routes.py", "src/tasks/routes.py"),
      edge("edge:repo:auth", "contains", "repository", "module:python:src/tasks/auth.py", "src/tasks/auth.py"),
      edge("edge:routes:entry", "contains", "module:python:src/tasks/routes.py", TASK_ROUTE.node_id, "src/tasks/routes.py"),
      edge("edge:auth:symbol", "contains", "module:python:src/tasks/auth.py", TASK_AUTH.node_id, "src/tasks/auth.py"),
      edge("edge:entry:auth", "depends_on", TASK_ROUTE.node_id, TASK_AUTH.node_id, "src/tasks/routes.py"),
      edge("edge:entry:postgres", "depends_on", TASK_ROUTE.node_id, "dependency:postgres", "src/tasks/routes.py"),
    ],
    diagnostics: [],
    summary: {
      language_count: 1,
      node_count: 6,
      edge_count: 6,
      module_count: 2,
      symbol_count: 1,
      entry_point_count: 1,
      external_dependency_count: 1,
      dependency_count: 2,
      diagnostic_count: 0,
    },
  },
} as const;

function answerForCitation(question: string, sampleId: string): SampleCitation[] {
  const terms = question.toLowerCase();
  if (sampleId === "sample_commerce_platform") {
    if (terms.includes("order") || terms.includes("create")) return [COMMERCE_ORDER, COMMERCE_ROUTE];
  }
  if (sampleId === "sample_task_api") {
    if (terms.includes("auth") || terms.includes("user")) return [TASK_AUTH, TASK_ROUTE];
  }
  return [];
}

export function getSampleRepository(analysisId: string): SampleRepository | null {
  return SAMPLE_BY_ID.get(analysisId) ?? null;
}

export function getSampleArchitecture(analysisId: string) {
  return SAMPLE_ARCHITECTURES[analysisId as keyof typeof SAMPLE_ARCHITECTURES] ?? null;
}

export function getSampleStatus(analysisId: string) {
  const sample = getSampleRepository(analysisId);
  if (!sample) return null;
  return {
    analysis_id: sample.analysisId,
    status: "completed",
    repository: {
      provider: "sample",
      owner: "repolume",
      repository: sample.name.toLowerCase().replaceAll(" ", "-"),
      canonical_url: `sample://${sample.analysisId}`,
      ref: null,
    },
    result_available: true,
    failure: null,
  };
}

export function getSampleAnswer(analysisId: string, payload: RepositoryQuestion) {
  if (!getSampleRepository(analysisId)) return null;
  const citations = answerForCitation(payload.question, analysisId);
  if (citations.length === 0) {
    return {
      schema_version: "1.0",
      question: payload.question,
      answer:
        "RepoLume could not find enough source evidence in this sample to answer that. Try asking about orders, auth, routes, or users.",
      grounding_status: "insufficient_evidence",
      citations: [],
    };
  }
  const primary = citations[0];
  const location = `${primary.location.path}:${primary.location.line}-${primary.location.end_line}`;
  return {
    schema_version: "1.0",
    question: payload.question,
    answer:
      `The sample evidence points to ${primary.name} at ${location} [1]. ` +
      "This is a static demo answer, so inspect the cited lines before treating it as runtime behavior.",
    grounding_status: "supported",
    citations,
  };
}
