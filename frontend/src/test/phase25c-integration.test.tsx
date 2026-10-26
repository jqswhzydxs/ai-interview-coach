import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import agentRunning from "@phase25a/mocks/agent-running.json";
import {
  createEvaluation,
  getAgentRun,
  getEvaluation,
} from "@/api/client";
import type { ApiError } from "@/api/client";
import { server } from "@/mocks/server";

import { renderRoute } from "./render";

describe("Phase 2.5C client boundaries", () => {
  it("rejects an unsupported upload before submission and keeps text entry available", async () => {
    renderRoute("/prep/new");
    const input = screen.getByLabelText("上传简历文件");
    fireEvent.change(input, {
      target: {
        files: [new File(["synthetic"], "resume.exe", { type: "application/octet-stream" })],
      },
    });

    expect(screen.getByRole("alert")).toHaveTextContent("请检查当前步骤");
    expect(screen.getByText("仅支持 PDF、DOCX 或 TXT 文件。")).toBeVisible();
    expect(screen.getByLabelText("简历内容")).toBeEnabled();
  });

  it("does not submit while the final Next button becomes the review submit button", async () => {
    const user = userEvent.setup();
    let documentPosts = 0;
    server.use(
      http.post("*/api/v1/documents/text", async ({ request }) => {
        documentPosts += 1;
        const body = (await request.json()) as { document_type: string };
        return HttpResponse.json({
          data: {
            source_document_id: body.document_type === "resume"
              ? "00000000-0000-4000-8000-000000000101"
              : "00000000-0000-4000-8000-000000000102",
            document_type: body.document_type,
            input_type: "text",
            original_filename: null,
            file_path: null,
            text_hash: "synthetic-hash",
            metadata: {},
            created_at: "2026-10-25T00:00:00Z",
          },
          message: "ok",
          request_id: "no-early-submit",
        });
      }),
    );
    renderRoute("/prep/new");
    await user.type(screen.getByLabelText("简历内容"), "合成简历内容超过十个字符用于测试");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.type(screen.getByLabelText("职位描述（JD）"), "合成职位描述超过十个字符用于测试");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "下一步" }));

    expect(screen.getByRole("heading", { name: "确认提交" })).toBeVisible();
    expect(screen.getByRole("button", { name: "生成准备包" })).toBeEnabled();
    expect(documentPosts).toBe(0);
  });

  it("turns an incompatible success payload into a nonretryable contract error", async () => {
    server.use(
      http.get("*/api/v1/evaluations/:evaluationId", () =>
        HttpResponse.json(
          { data: { score_available: false, total_score: 0 }, message: "ok", request_id: "bad-contract" },
          { headers: { "x-request-id": "bad-contract" } },
        )),
    );

    await expect(getEvaluation("00000000-0000-4000-8000-000000000601")).rejects.toMatchObject({
      code: "RESPONSE_CONTRACT_ERROR",
      retryable: false,
      requestId: "bad-contract",
    } satisfies Partial<ApiError>);
  });

  it("parses Retry-After without exposing the provider response message", async () => {
    server.use(
      http.post("*/api/v1/evaluations", () =>
        HttpResponse.json(
          {
            error: {
              code: "AGENT_FAILED",
              message: "raw provider detail must stay hidden",
              details: { failure_category: "network" },
            },
          },
          {
            status: 503,
            headers: { "retry-after": "2", "x-request-id": "safe-request-id" },
          },
        )),
    );

    await expect(createEvaluation({ custom_question_text: "Synthetic question", user_answer: "Synthetic answer" }))
      .rejects.toMatchObject({
        message: "服务暂时不可用，请稍后重试。",
        retryAfterMs: 2000,
        requestId: "safe-request-id",
      } satisfies Partial<ApiError>);
  });

  it("strips AgentRun input/output summaries and raw errors at the runtime boundary", async () => {
    const run = await getAgentRun("00000000-0000-4000-8000-000000000501");
    expect(run).not.toHaveProperty("input_summary");
    expect(run).not.toHaveProperty("output_summary");
    expect(run).not.toHaveProperty("error_message");
    expect(run.steps[0]).not.toHaveProperty("error_message");
  });

  it("polls only while AgentRun is nonterminal and stops after success", async () => {
    let calls = 0;
    const source = structuredClone(agentRunning.steps[0]?.response?.body) as {
      data: { status: string; steps: Array<{ status: string }> };
      message: string;
      request_id: string;
    };
    server.use(
      http.get("*/api/v1/agent-runs/:agentRunId", () => {
        calls += 1;
        const body = structuredClone(source);
        if (calls > 1) {
          body.data.status = "succeeded";
          for (const step of body.data.steps) step.status = "succeeded";
        }
        return HttpResponse.json(body, {
          headers: { "retry-after": "0.01", "x-request-id": `poll-${calls}` },
        });
      }),
    );

    renderRoute("/prep/00000000-0000-4000-8000-000000000401/processing?agentRunId=00000000-0000-4000-8000-000000000501");
    expect(await screen.findByRole("heading", { name: "任务状态：succeeded" })).toBeVisible();
    const terminalCalls = calls;
    await new Promise((resolve) => window.setTimeout(resolve, 50));
    expect(calls).toBe(terminalCalls);
  });
});
