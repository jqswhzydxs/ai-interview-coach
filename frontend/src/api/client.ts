import type { z } from "zod";

import type { components } from "./generated/openapi";
import {
  agentRunSchema,
  apiErrorEnvelopeSchema,
  documentCreatedSchema,
  evaluationCreatedSchema,
  evaluationDetailSchema,
  evaluationHistorySchema,
  experienceCreatedSchema,
  experienceParsedSchema,
  jobCreatedSchema,
  jobParsedSchema,
  prepPackageCreatedSchema,
  prepPackageDetailSchema,
  questionListSchema,
  resumeCreatedSchema,
  resumeParsedSchema,
  successEnvelopeSchema,
  type AgentRun,
  type DocumentCreated,
  type EvaluationCreated,
  type EvaluationDetail,
  type EvaluationHistory,
  type ExperienceCreated,
  type JobCreated,
  type PrepPackageDetail,
  type QuestionList,
  type ResumeCreated,
} from "./domain";

export type TextDocumentCreate = components["schemas"]["TextDocumentCreate"];
export type ResumeCreate = components["schemas"]["ResumeCreate"];
export type JobDescriptionCreate = components["schemas"]["JobDescriptionCreate"];
export type ExperienceCreate = components["schemas"]["ExperienceCreate"];
export type PrepPackageCreate = components["schemas"]["PrepPackageCreate"];
export type EvaluationCreate = components["schemas"]["EvaluationCreate"];
export type DocumentType = TextDocumentCreate["document_type"];

export const isMockMode = import.meta.env.VITE_USE_MOCKS !== "false";
const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const defaultTimeoutMs = 120_000;

export interface ApiResult<T> {
  value: T;
  requestId: string | null;
  retryAfterMs: number | null;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId: string | null;
  readonly retryable: boolean;
  readonly failureCategory: string | null;
  readonly retryAfterMs: number | null;

  constructor(options: {
    code: string;
    status: number;
    requestId: string | null;
    retryable: boolean;
    failureCategory?: string | null;
    retryAfterMs?: number | null;
  }) {
    super(safeErrorMessage(options.code));
    this.name = "ApiError";
    this.code = options.code;
    this.status = options.status;
    this.requestId = options.requestId;
    this.retryable = options.retryable;
    this.failureCategory = options.failureCategory ?? null;
    this.retryAfterMs = options.retryAfterMs ?? null;
  }
}

const safeErrorMessage = (code: string): string => {
  if (code === "VALIDATION_ERROR") return "提交内容不符合要求，请检查后重试。";
  if (code === "NOT_FOUND") return "未找到对应内容，请返回上一页。";
  if (code === "AGENT_FAILED") return "服务暂时不可用，请稍后重试。";
  if (code === "RESPONSE_CONTRACT_ERROR") return "服务响应与已冻结合同不一致。";
  return "请求未完成，请稍后重试。";
};

const absoluteUrl = (path: string): string => {
  const base = configuredBaseUrl.endsWith("/")
    ? configuredBaseUrl.slice(0, -1)
    : configuredBaseUrl;
  const relativePath = path.startsWith("/") ? path : `/${path}`;
  if (/^https?:\/\//u.test(base)) return `${base}${relativePath}`;
  return new URL(`${base}${relativePath}`, window.location.origin).toString();
};

const parseRetryAfter = (value: string | null): number | null => {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.min(seconds * 1000, 30_000);
  const at = Date.parse(value);
  if (!Number.isFinite(at)) return null;
  return Math.min(Math.max(0, at - Date.now()), 30_000);
};

const controlledSignal = (
  upstream: AbortSignal | undefined,
  timeoutMs: number,
): { signal: AbortSignal; cleanup: () => void } => {
  const controller = new AbortController();
  const forwardAbort = () => controller.abort(upstream?.reason);
  if (upstream?.aborted) forwardAbort();
  else upstream?.addEventListener("abort", forwardAbort, { once: true });
  const timeoutId = window.setTimeout(
    () => controller.abort(new DOMException("Request deadline exceeded", "TimeoutError")),
    timeoutMs,
  );
  return {
    signal: controller.signal,
    cleanup: () => {
      window.clearTimeout(timeoutId);
      upstream?.removeEventListener("abort", forwardAbort);
    },
  };
};

export async function apiRequestResult<T>(options: {
  path: string;
  schema: z.ZodType<T>;
  method?: "GET" | "POST";
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal | undefined;
  scenario?: string | undefined;
  timeoutMs?: number | undefined;
}): Promise<ApiResult<T>> {
  const headers = new Headers({ Accept: "application/json" });
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  if (isMockMode && options.scenario) headers.set("x-mock-scenario", options.scenario);
  const guarded = controlledSignal(options.signal, options.timeoutMs ?? defaultTimeoutMs);
  const requestInit: RequestInit = {
    method: options.method ?? "GET",
    headers,
    signal: guarded.signal,
  };
  if (options.body !== undefined) requestInit.body = JSON.stringify(options.body);
  if (options.formData !== undefined) requestInit.body = options.formData;

  try {
    const response = await fetch(absoluteUrl(options.path), requestInit);
    const requestIdFromHeader = response.headers.get("x-request-id");
    const retryAfterMs = parseRetryAfter(response.headers.get("retry-after"));
    const payload: unknown = await response.json();
    if (!response.ok) {
      const parsed = apiErrorEnvelopeSchema.safeParse(payload);
      const code = parsed.success ? parsed.data.error.code : "UNKNOWN_ERROR";
      const category = parsed.success
        ? parsed.data.error.details.failure_category
        : undefined;
      throw new ApiError({
        code,
        status: response.status,
        requestId: requestIdFromHeader,
        retryable: [408, 429, 502, 503, 504].includes(response.status),
        failureCategory: typeof category === "string" ? category : null,
        retryAfterMs,
      });
    }
    const parsed = options.schema.safeParse(payload);
    if (!parsed.success) {
      throw new ApiError({
        code: "RESPONSE_CONTRACT_ERROR",
        status: response.status,
        requestId: requestIdFromHeader,
        retryable: false,
      });
    }
    return { value: parsed.data, requestId: requestIdFromHeader, retryAfterMs };
  } finally {
    guarded.cleanup();
  }
}

export async function apiRequest<T>(
  options: Parameters<typeof apiRequestResult<T>>[0],
): Promise<T> {
  return (await apiRequestResult(options)).value;
}

const mockScenario = (scenario: string | undefined, fallback: string): string | undefined =>
  isMockMode ? (scenario ?? fallback) : undefined;

export async function createTextDocument(
  body: TextDocumentCreate,
  signal?: AbortSignal,
): Promise<DocumentCreated> {
  const result = await apiRequest({
    path: "/documents/text",
    method: "POST",
    body,
    signal,
    scenario: mockScenario(undefined, "standard-success"),
    schema: successEnvelopeSchema(documentCreatedSchema),
  });
  return result.data;
}

export async function uploadDocument(
  documentType: DocumentType,
  file: File,
  signal?: AbortSignal,
): Promise<DocumentCreated> {
  const formData = new FormData();
  formData.set("document_type", documentType);
  formData.set("file", file);
  const result = await apiRequest({
    path: "/documents/upload",
    method: "POST",
    formData,
    signal,
    scenario: mockScenario(undefined, "standard-success"),
    schema: successEnvelopeSchema(documentCreatedSchema),
  });
  return result.data;
}

export async function createResume(body: ResumeCreate, signal?: AbortSignal): Promise<ResumeCreated> {
  const result = await apiRequest({
    path: "/resumes",
    method: "POST",
    body,
    signal,
    scenario: mockScenario(undefined, "standard-success"),
    schema: successEnvelopeSchema(resumeCreatedSchema),
  });
  return result.data;
}

export async function parseResume(resumeId: string, signal?: AbortSignal): Promise<string> {
  const result = await apiRequest({
    path: `/resumes/${resumeId}/parse`,
    method: "POST",
    signal,
    scenario: mockScenario(undefined, "standard-success"),
    schema: successEnvelopeSchema(resumeParsedSchema),
  });
  return result.data.agent_run_id;
}

export async function createJob(
  body: JobDescriptionCreate,
  signal?: AbortSignal,
): Promise<JobCreated> {
  const result = await apiRequest({
    path: "/jobs",
    method: "POST",
    body,
    signal,
    scenario: mockScenario(undefined, "standard-success"),
    schema: successEnvelopeSchema(jobCreatedSchema),
  });
  return result.data;
}

export async function parseJob(jobId: string, signal?: AbortSignal): Promise<string> {
  const result = await apiRequest({
    path: `/jobs/${jobId}/parse`,
    method: "POST",
    signal,
    scenario: mockScenario(undefined, "standard-success"),
    schema: successEnvelopeSchema(jobParsedSchema),
  });
  return result.data.agent_run_id;
}

export async function createExperience(
  body: ExperienceCreate,
  signal?: AbortSignal,
): Promise<ExperienceCreated> {
  const result = await apiRequest({
    path: "/experiences",
    method: "POST",
    body,
    signal,
    scenario: mockScenario(undefined, "standard-success"),
    schema: successEnvelopeSchema(experienceCreatedSchema),
  });
  return result.data;
}

export async function parseExperience(experienceId: string, signal?: AbortSignal): Promise<string> {
  const result = await apiRequest({
    path: `/experiences/${experienceId}/parse`,
    method: "POST",
    signal,
    scenario: mockScenario(undefined, "standard-success"),
    schema: successEnvelopeSchema(experienceParsedSchema),
  });
  return result.data.agent_run_id;
}

export async function createPrepPackage(
  body: PrepPackageCreate,
  signal?: AbortSignal,
): Promise<z.infer<typeof prepPackageCreatedSchema>> {
  const result = await apiRequest({
    path: "/prep-packages",
    method: "POST",
    body,
    signal,
    scenario: mockScenario(undefined, "standard-success"),
    schema: successEnvelopeSchema(prepPackageCreatedSchema),
  });
  return result.data;
}

export async function getPrepPackage(
  prepPackageId: string,
  signal?: AbortSignal,
): Promise<PrepPackageDetail> {
  const result = await apiRequest({
    path: `/prep-packages/${prepPackageId}`,
    signal,
    scenario: mockScenario(undefined, "standard-success"),
    schema: successEnvelopeSchema(prepPackageDetailSchema),
  });
  return result.data;
}

export async function getQuestions(
  prepPackageId: string,
  scenario?: string,
  signal?: AbortSignal,
): Promise<QuestionList> {
  const result = await apiRequest({
    path: `/prep-packages/${prepPackageId}/questions`,
    signal,
    scenario: mockScenario(scenario, "standard-success"),
    schema: successEnvelopeSchema(questionListSchema),
  });
  return result.data;
}

export async function getEvaluation(
  evaluationId: string,
  scenario?: string,
  signal?: AbortSignal,
): Promise<EvaluationDetail> {
  const result = await apiRequest({
    path: `/evaluations/${evaluationId}`,
    signal,
    scenario: mockScenario(scenario, "standard-evaluation"),
    schema: successEnvelopeSchema(evaluationDetailSchema),
  });
  return result.data;
}

export async function listEvaluations(signal?: AbortSignal): Promise<EvaluationHistory> {
  const result = await apiRequest({
    path: "/evaluations?limit=20&offset=0",
    signal,
    scenario: mockScenario(undefined, "empty-history"),
    schema: successEnvelopeSchema(evaluationHistorySchema),
  });
  return result.data;
}

export async function getAgentRunWithMeta(
  agentRunId: string,
  scenario?: string,
  signal?: AbortSignal,
): Promise<ApiResult<AgentRun>> {
  const result = await apiRequestResult({
    path: `/agent-runs/${agentRunId}`,
    signal,
    scenario: mockScenario(scenario, "agent-running"),
    schema: successEnvelopeSchema(agentRunSchema),
  });
  return {
    value: result.value.data,
    requestId: result.requestId,
    retryAfterMs: result.retryAfterMs,
  };
}

export async function getAgentRun(
  agentRunId: string,
  scenario?: string,
  signal?: AbortSignal,
): Promise<AgentRun> {
  return (await getAgentRunWithMeta(agentRunId, scenario, signal)).value;
}

export async function createEvaluation(
  body: EvaluationCreate,
  scenario?: string,
  signal?: AbortSignal,
): Promise<EvaluationCreated> {
  const result = await apiRequest({
    path: "/evaluations",
    method: "POST",
    body,
    signal,
    scenario: mockScenario(scenario, "standard-evaluation-create"),
    schema: successEnvelopeSchema(evaluationCreatedSchema),
  });
  return result.data;
}
