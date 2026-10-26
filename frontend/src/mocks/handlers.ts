import { delay, http, HttpResponse, type HttpHandler, type JsonBodyType } from "msw";

import { mockScenarios } from "./scenarios";
import type { MockStep } from "./types";

const routes = [
  ["POST", "*/api/v1/documents/text"],
  ["POST", "*/api/v1/prep-packages"],
  ["GET", "*/api/v1/prep-packages/:prepPackageId"],
  ["GET", "*/api/v1/prep-packages/:prepPackageId/questions"],
  ["POST", "*/api/v1/resumes"],
  ["POST", "*/api/v1/resumes/:resumeId/parse"],
  ["POST", "*/api/v1/jobs"],
  ["POST", "*/api/v1/jobs/:jobId/parse"],
  ["POST", "*/api/v1/experiences"],
  ["POST", "*/api/v1/experiences/:experienceId/parse"],
  ["GET", "*/api/v1/agent-runs/:agentRunId"],
  ["GET", "*/api/v1/evaluations/:evaluationId"],
  ["GET", "*/api/v1/evaluations"],
  ["POST", "*/api/v1/evaluations"],
  ["POST", "*/api/v1/documents/upload"],
] as const;

const normalizePath = (value: string): string =>
  value.replace(
    /\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?=\/|$)/giu,
    "/:id",
  );

const findStep = (scenarioId: string, method: string, pathname: string): MockStep | undefined => {
  const scenario = mockScenarios[scenarioId];
  if (!scenario) return undefined;
  const normalized = normalizePath(pathname);
  const step = scenario.steps.find(
    (candidate) =>
      candidate.method === method && normalizePath(candidate.path) === normalized,
  );
  return step;
};

const mockEnvelope = (data: JsonBodyType, requestId: string) =>
  HttpResponse.json(
    { data, message: "ok", request_id: requestId },
    { headers: { "x-request-id": requestId } },
  );

const standardWorkflowResponse = async (request: Request, pathname: string) => {
  const requestId = "mock-standard-workflow";
  if (request.method === "POST" && pathname.endsWith("/documents/text")) {
    const body = (await request.json()) as { document_type?: string };
    const ids: Record<string, string> = {
      resume: "00000000-0000-4000-8000-000000000101",
      jd: "00000000-0000-4000-8000-000000000102",
      interview_experience: "00000000-0000-4000-8000-000000000103",
    };
    return mockEnvelope({
      source_document_id: ids[body.document_type ?? "resume"],
      document_type: body.document_type,
      input_type: "text",
      original_filename: null,
      file_path: null,
      text_hash: "mock-text-hash",
      metadata: {},
      created_at: "2026-10-24T08:00:00Z",
    }, requestId);
  }
  if (request.method === "POST" && pathname.endsWith("/documents/upload")) {
    return mockEnvelope({
      source_document_id: "00000000-0000-4000-8000-000000000101",
      document_type: "resume",
      input_type: "upload",
      original_filename: "synthetic-resume.txt",
      file_path: "mock-only-redacted",
      text_hash: "mock-upload-hash",
      metadata: { input_type: "text", size_bytes: 64 },
      created_at: "2026-10-24T08:00:00Z",
    }, requestId);
  }
  if (request.method === "POST" && pathname.endsWith("/resumes")) {
    return mockEnvelope({
      resume_id: "00000000-0000-4000-8000-000000000201",
      source_document_id: "00000000-0000-4000-8000-000000000101",
      title: "合成后端简历",
      target_direction: "backend",
      version_label: null,
      is_active: true,
      created_at: "2026-10-24T08:00:00Z",
    }, requestId);
  }
  if (request.method === "POST" && /\/resumes\/[^/]+\/parse$/u.test(pathname)) {
    return mockEnvelope({
      resume_id: "00000000-0000-4000-8000-000000000201",
      resume_profile_id: "00000000-0000-4000-8000-000000000211",
      agent_run_id: "00000000-0000-4000-8000-000000000511",
    }, requestId);
  }
  if (request.method === "POST" && pathname.endsWith("/jobs")) {
    return mockEnvelope({
      job_description_id: "00000000-0000-4000-8000-000000000301",
      source_document_id: "00000000-0000-4000-8000-000000000102",
      title: "合成后端岗位",
      company_name: null,
      job_url: null,
      target_direction: "backend",
      created_at: "2026-10-24T08:00:00Z",
    }, requestId);
  }
  if (request.method === "POST" && /\/jobs\/[^/]+\/parse$/u.test(pathname)) {
    return mockEnvelope({
      job_description_id: "00000000-0000-4000-8000-000000000301",
      jd_profile_id: "00000000-0000-4000-8000-000000000311",
      agent_run_id: "00000000-0000-4000-8000-000000000512",
    }, requestId);
  }
  if (request.method === "POST" && pathname.endsWith("/experiences")) {
    return mockEnvelope({
      interview_experience_id: "00000000-0000-4000-8000-000000000801",
      source_document_id: "00000000-0000-4000-8000-000000000103",
      title: "合成面经",
      experience_type: "manual",
      company_name: null,
      role_name: null,
      created_at: "2026-10-24T08:00:00Z",
    }, requestId);
  }
  if (request.method === "POST" && /\/experiences\/[^/]+\/parse$/u.test(pathname)) {
    return mockEnvelope({
      interview_experience_id: "00000000-0000-4000-8000-000000000801",
      experience_profile_id: "00000000-0000-4000-8000-000000000811",
      agent_run_id: "00000000-0000-4000-8000-000000000513",
    }, requestId);
  }
  if (request.method === "GET" && /\/prep-packages\/[^/]+$/u.test(pathname)) {
    return mockEnvelope({
      prep_package_id: "00000000-0000-4000-8000-000000000401",
      title: "合成后端面试准备包",
      status: "ready",
      overview: { preparation_goal: "后端面试练习" },
      question_count: 25,
      recommended_count: 3,
      created_at: "2026-10-24T08:00:00Z",
    }, requestId);
  }
  return undefined;
};

const evaluationCreateResponse = (pathname: string, method: string) => {
  if (method !== "POST" || !pathname.endsWith("/evaluations")) return undefined;
  return mockEnvelope({
    answer_evaluation_id: "00000000-0000-4000-8000-000000000601",
    agent_run_id: "00000000-0000-4000-8000-000000000501",
    evaluation_mode: "standard",
    score_available: true,
    source_quality: "trusted",
    degradation_reasons: [],
    total_score: 80,
  }, "mock-standard-evaluation-create");
};

const resolver = async ({ request }: { request: Request }) => {
  const scenarioId = request.headers.get("x-mock-scenario");
  if (!scenarioId) {
    return HttpResponse.json(
      { error: { code: "MOCK_SCENARIO_REQUIRED", message: "Mock scenario required", details: {} } },
      { status: 500 },
    );
  }
  const pathname = new URL(request.url).pathname;
  if (
    scenarioId === "visual-loading"
    && request.method === "GET"
    && /\/evaluations\/[^/]+$/u.test(pathname)
  ) {
    await delay("infinite");
    return new HttpResponse(null, { status: 204 });
  }
  if (
    scenarioId === "visual-retryable-error"
    && request.method === "GET"
    && /\/evaluations\/[^/]+$/u.test(pathname)
  ) {
    return HttpResponse.json(
      {
        error: {
          code: "AGENT_FAILED",
          message: "Synthetic provider detail",
          details: { failure_category: "network" },
        },
      },
      {
        status: 503,
        headers: { "retry-after": "1", "x-request-id": "visual-safe-request-id" },
      },
    );
  }
  const step = findStep(scenarioId, request.method, pathname);
  if (!step && scenarioId === "standard-success") {
    const response = await standardWorkflowResponse(request, pathname);
    if (response) return response;
  }
  if (!step && scenarioId === "question-bank-fallback") {
    const response = await standardWorkflowResponse(request, pathname);
    if (response) return response;
  }
  if (!step && scenarioId === "standard-evaluation-create") {
    const response = evaluationCreateResponse(pathname, request.method);
    if (response) return response;
  }
  if (!step) {
    return HttpResponse.json(
      { error: { code: "MOCK_STEP_MISSING", message: "Mock step missing", details: {} } },
      { status: 500 },
    );
  }
  if (step.response === null) {
    await delay("infinite");
    return new HttpResponse(null, { status: 204 });
  }
  const requestId =
    step.request.headers["x-request-id"] ?? `mock-${step.name}`;
  return HttpResponse.json(step.response.body as JsonBodyType, {
    status: step.response.status_code,
    headers: { "x-request-id": requestId },
  });
};

export const handlers: HttpHandler[] = routes.map(([method, path]) =>
  method === "GET" ? http.get(path, resolver) : http.post(path, resolver),
);
