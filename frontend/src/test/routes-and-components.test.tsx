import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import standardSuccess from "@phase25a/mocks/standard-success.json";
import { RetryPanel } from "@/components/Feedback";
import { QuestionBankTabs } from "@/components/Questions";
import { server } from "@/mocks/server";

import { renderRoute } from "./render";

const prepId = "00000000-0000-4000-8000-000000000401";

describe("routes, deep links and component state", () => {
  it("renders a deep-linked question bank and its fallback explanation", async () => {
    renderRoute(`/prep/${prepId}/questions?scenario=question-bank-fallback`);
    expect(await screen.findByRole("heading", { name: "面试题库" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "当前结果已降级" })).toBeVisible();
    expect(screen.getByText("题库生成使用了安全 fallback。")).toBeVisible();
    expect(screen.getByRole("tab", { name: /自我介绍/u })).toHaveAttribute("aria-selected", "true");
  });

  it("keeps question tabs keyboard operable", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderRoute(
      "/",
      <QuestionBankTabs
        counts={{ self_intro: 8, professional: 8, behavior_project: 9 }}
        activeModule="self_intro"
        onChange={onChange}
      >
        <p>当前模块</p>
      </QuestionBankTabs>,
    );
    const firstTab = screen.getByRole("tab", { name: /自我介绍/u });
    firstTab.focus();
    await user.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenCalledWith("professional");
    expect(screen.getByRole("tab", { name: /专业问题/u })).toHaveFocus();
  });

  it("supports the full multi-step form and disables duplicate submission", async () => {
    let requestCount = 0;
    server.use(
      http.post("*/api/v1/prep-packages", async () => {
        requestCount += 1;
        await delay(60);
        return HttpResponse.json(standardSuccess.steps[0]?.response?.body);
      }),
    );
    const user = userEvent.setup();
    renderRoute("/prep/new");
    await user.type(screen.getByLabelText("简历内容"), "这是仅用于合同测试的合成简历内容。Java 后端开发。 ");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.type(screen.getByLabelText("职位描述（JD）"), "这是仅用于合同测试的合成职位描述，要求后端开发。 ");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    expect(screen.getByLabelText(/面经内容/u)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "下一步" }));
    const submit = screen.getByRole("button", { name: "生成准备包" });
    await user.dblClick(submit);
    expect(await screen.findByRole("heading", { name: "生成进度" })).toBeVisible();
    expect(requestCount).toBe(1);
  });

  it("renders retryable and nonretryable recovery affordances", () => {
    const retry = vi.fn();
    renderRoute(
      "/",
      <RetryPanel
        title="请求失败"
        reason="服务暂时不可用，请稍后重试。"
        retryable
        requestId="mock-safe-request-id"
        onRetry={retry}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("mock-safe-request-id");
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("omits retry for a nonretryable contract error", () => {
    renderRoute(
      "/",
      <RetryPanel
        title="提交内容不符合合同"
        reason="请返回修改。"
        retryable={false}
        onEdit={() => undefined}
      />,
    );
    expect(screen.queryByRole("button", { name: "重试" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "返回修改" })).toBeVisible();
  });

  it("renders the empty history state", async () => {
    renderRoute("/history");
    expect(await screen.findByRole("heading", { name: "还没有练习记录" })).toBeVisible();
    expect(screen.getAllByRole("link", { name: "创建准备任务" }).length).toBeGreaterThan(0);
  });

  it("closes mobile navigation with Escape and restores trigger focus", async () => {
    const user = userEvent.setup();
    renderRoute("/");
    const trigger = screen.getByRole("button", { name: "打开导航" });
    await user.click(trigger);
    expect(screen.getByRole("button", { name: "关闭导航" })).toBeVisible();
    await user.keyboard("{Escape}");
    expect(await screen.findByRole("button", { name: "打开导航" })).toHaveFocus();
  });

  it("announces processing progress without submitting another request", async () => {
    renderRoute(`/prep/${prepId}/processing?agentRunId=00000000-0000-4000-8000-000000000501&scenario=agent-running`);
    expect(await screen.findByRole("heading", { name: "生成进度" })).toBeVisible();
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText(/不会自动触发下一阶段请求/u)).toBeVisible();
  });
});
