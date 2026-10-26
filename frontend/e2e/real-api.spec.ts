import { expect, test } from "@playwright/test";

import {
  enforceLoopbackOnly,
  expectMinimumTargets,
  expectNoHorizontalOverflow,
  expectNoSeriousAxeViolations,
} from "./support";

test.describe.serial("Phase 2.5C real FastAPI flow", () => {
  test("uses returned IDs across create, parse, questions, evaluation, history and AgentRun", async ({ page }) => {
    const blocked = await enforceLoopbackOnly(page);
    const requestHeaders: Array<Record<string, string>> = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/v1/")) requestHeaders.push(request.headers());
    });

    await page.goto("/prep/new");
    await page.getByLabel("简历内容").fill(
      "合成测试简历：三年 Python、FastAPI 和 PostgreSQL 后端经验，负责接口可靠性与自动化测试。",
    );
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByLabel("职位描述（JD）").fill(
      "合成测试岗位：负责 Python 后端服务、API 设计、数据库性能、可靠性治理和跨团队交付。",
    );
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByLabel("面经内容").fill("合成面经：关注接口边界、数据库优化和故障恢复。" );
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByRole("button", { name: "生成准备包" }).click();

    await expect(page).toHaveURL(/\/prep\/[0-9a-f-]+\/processing\?agentRunId=[0-9a-f-]+$/u);
    const processingUrl = new URL(page.url());
    const agentRunId = processingUrl.searchParams.get("agentRunId");
    expect(agentRunId).toMatch(/^[0-9a-f-]{36}$/u);
    await expect(page.getByText("任务状态：succeeded")).toBeVisible();
    await page.getByRole("link", { name: "查看题库" }).click();

    await expect(page.getByRole("heading", { name: "面试题库" })).toBeVisible();
    await expect(page.getByRole("tab", { name: /自我介绍 \(8\)/u })).toBeVisible();
    await expect(page.getByRole("tab", { name: /专业问题 \(8\)/u })).toBeVisible();
    await expect(page.getByRole("tab", { name: /行为与项目 \(9\)/u })).toBeVisible();
    await page.getByRole("link", { name: /开始练习/u }).first().click();

    await page.getByLabel("你的回答").fill(
      "我先确认接口目标和约束，再用自动化测试验证正常、异常与并发路径，并根据监控结果复盘。",
    );
    await page.getByRole("button", { name: "提交回答" }).click();
    await expect(page.getByRole("heading", { name: "本次回答反馈" })).toBeVisible();
    await expect(page.getByLabel("总分")).toBeVisible();
    await page.screenshot({
      path: "e2e/__screenshots__/real-api/real-api-happy-path.png",
      fullPage: true,
    });

    await page.getByRole("link", { name: "练习历史" }).click();
    await expect(page.getByRole("heading", { name: "练习历史" })).toBeVisible();
    await expect(page.getByRole("link", { name: "查看评价" })).toHaveCount(1);

    await page.goto(`/agent-runs/${agentRunId}`);
    await expect(page.getByRole("heading", { name: "运行详情" })).toBeVisible();
    await expect(page.getByText("执行模式：mock")).toBeVisible();
    await expect(page.getByText("真实调用次数").locator(".." )).toContainText("0");

    expect(requestHeaders.length).toBeGreaterThan(0);
    expect(requestHeaders.every((headers) => headers["x-mock-scenario"] === undefined)).toBe(true);
    expect(blocked).toEqual([]);
    await expectNoHorizontalOverflow(page);
    await expectMinimumTargets(page);
    await expectNoSeriousAxeViolations(page);
  });

  test("recovers from a server-rejected upload without a duplicate POST", async ({ page }) => {
    const blocked = await enforceLoopbackOnly(page);
    let uploadPosts = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith("/api/v1/documents/upload")) uploadPosts += 1;
    });
    await page.goto("/prep/new");
    await page.getByLabel("上传简历文件").setInputFiles({
      name: "synthetic-invalid.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("not a pdf signature"),
    });
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByLabel("职位描述（JD）").fill("合成测试岗位要求至少十个字符并覆盖后端可靠性。" );
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByRole("button", { name: "生成准备包" }).click();
    await expect(page.getByRole("alert")).toContainText("准备任务未创建");
    await expect(page.getByRole("alert")).not.toContainText("not a pdf signature");
    expect(uploadPosts).toBe(1);
    await page.getByRole("button", { name: "返回修改" }).click();
    await expect(page.getByLabel("简历内容")).toBeVisible();
    expect(blocked).toEqual([]);
  });

  test("supports keyboard validation recovery and restores focus", async ({ page }) => {
    await enforceLoopbackOnly(page);
    await page.goto("/prep/new");
    await page.getByRole("button", { name: "下一步" }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("alert")).toBeFocused();
    await page.getByLabel("简历内容").fill("合成键盘流程简历内容超过十个字符。" );
    await page.getByRole("button", { name: "下一步" }).press("Enter");
    await expect(page.getByLabel("职位描述（JD）")).toBeVisible();
  });
});
