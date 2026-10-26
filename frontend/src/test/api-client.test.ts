import { describe, expect, it } from "vitest";

import { createEvaluation, getEvaluation, getQuestions } from "@/api/client";
import type { ApiError } from "@/api/client";
import { mockScenarios } from "@/mocks/scenarios";

const evaluationBody = {
  question_db_id: "00000000-0000-4000-8000-000000000701",
  custom_question_text: null,
  user_answer: "合成回答。",
};

describe("API client and strict MSW runtime", () => {
  it("parses standard and degraded evaluations with their distinct score semantics", async () => {
    const standard = await getEvaluation("00000000-0000-4000-8000-000000000601");
    expect(standard.score_available).toBe(true);
    expect(standard.total_score).toEqual(expect.any(Number));
    expect(standard.evaluation.dimension_scores.length).toBeGreaterThan(0);

    const degraded = await getEvaluation(
      "00000000-0000-4000-8000-000000000601",
      "evaluator-degraded",
    );
    expect(degraded.score_available).toBe(false);
    expect(degraded.total_score).toBeNull();
    expect(degraded.evaluation.dimension_scores).toEqual([]);
  });

  it("preserves the strict 8/8/9 question distribution", async () => {
    const questions = await getQuestions("00000000-0000-4000-8000-000000000401");
    expect(questions.items.filter((item) => item.module === "self_intro")).toHaveLength(8);
    expect(questions.items.filter((item) => item.module === "professional")).toHaveLength(8);
    expect(questions.items.filter((item) => item.module === "behavior_project")).toHaveLength(9);
  });

  it("normalizes retryable provider errors without exposing the raw message", async () => {
    await expect(createEvaluation(evaluationBody, "retryable-provider-error")).rejects.toMatchObject({
      code: "AGENT_FAILED",
      retryable: true,
      requestId: "mock-retryable-provider-failure",
      failureCategory: "network",
      message: "服务暂时不可用，请稍后重试。",
    } satisfies Partial<ApiError>);
  });

  it("marks contract errors nonretryable", async () => {
    await expect(
      createEvaluation({ custom_question_text: null, question_db_id: null, user_answer: "" }, "nonretryable-contract-error"),
    ).rejects.toMatchObject({
      code: "VALIDATION_ERROR",
      retryable: false,
      requestId: "mock-invalid-evaluation-request",
    } satisfies Partial<ApiError>);
  });

  it("cancels an in-flight mock request through AbortSignal", async () => {
    const controller = new AbortController();
    const request = createEvaluation(evaluationBody, "request-cancelled-timeout", controller.signal);
    controller.abort();
    await expect(request).rejects.toMatchObject({ name: "AbortError" });
  });

  it("fails unmatched network requests instead of bypassing MSW", async () => {
    await expect(fetch("http://localhost/api/v1/unregistered-route")).rejects.toThrow();
  });

  it("serves every completed step in all 12 versioned scenarios", async () => {
    for (const scenario of Object.values(mockScenarios)) {
      for (const step of scenario.steps.filter((item) => item.response !== null)) {
        const headers = new Headers({ "x-mock-scenario": scenario.scenario_id });
        const init: RequestInit = { method: step.method, headers };
        if (step.method !== "GET" && step.request.body !== null) {
          headers.set("content-type", "application/json");
          init.body = JSON.stringify(step.request.body);
        }
        const response = await fetch(`http://localhost${step.path}`, init);
        expect(response.status, `${scenario.scenario_id}:${step.name}`).toBe(step.response?.status_code);
        expect(response.headers.get("x-request-id")).toBe(step.request.headers["x-request-id"]);
      }
    }
  });
});
