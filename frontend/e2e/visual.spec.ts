import { expect, test } from "@playwright/test";

import {
  enforceLoopbackOnly,
  expectMinimumTargets,
  expectNoHorizontalOverflow,
  expectNoSeriousAxeViolations,
} from "./support";

const evaluationId = "00000000-0000-4000-8000-000000000601";
const packageId = "00000000-0000-4000-8000-000000000401";
const agentRunId = "00000000-0000-4000-8000-000000000501";

test.describe("Phase 2.5C deterministic visual baselines", () => {
  test.beforeEach(async ({ page }) => {
    await enforceLoopbackOnly(page);
    await page.emulateMedia({ reducedMotion: "reduce" });
  });

  for (const width of [375, 768, 1024, 1440]) {
    test(`standard evaluation at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: width === 375 ? 812 : 900 });
      await page.goto(`/evaluations/${evaluationId}?scenario=standard-evaluation`);
      await expect(page.getByRole("heading", { name: "本次回答反馈" })).toBeVisible();
      await expectNoHorizontalOverflow(page);
      await expectMinimumTargets(page);
      await expectNoSeriousAxeViolations(page);
      await expect(page).toHaveScreenshot(`standard-evaluation-${width}.png`, { fullPage: true });
    });
  }

  const states = [
    {
      name: "degraded-no-score",
      path: `/evaluations/${evaluationId}?scenario=evaluator-degraded`,
      text: "本次无法提供可信分数",
    },
    {
      name: "memory-blocked",
      path: `/evaluations/${evaluationId}?scenario=memory-write-blocked`,
      text: "本次结果未写入长期记忆",
    },
    {
      name: "question-bank-fallback",
      path: `/prep/${packageId}/questions?scenario=question-bank-fallback`,
      text: "当前结果已降级",
    },
    {
      name: "upstream-fallback",
      path: `/agent-runs/${agentRunId}?scenario=upstream-fallback`,
      text: "当前结果已降级",
    },
    {
      name: "loading",
      path: `/evaluations/${evaluationId}?scenario=visual-loading`,
      text: "正在加载评价结果",
    },
    {
      name: "retryable-error",
      path: `/evaluations/${evaluationId}?scenario=visual-retryable-error`,
      text: "评价结果暂时不可用",
    },
    {
      name: "not-found",
      path: "/not-a-real-route",
      text: "页面不存在",
    },
  ];

  for (const state of states) {
    test(state.name, async ({ page }) => {
      await page.setViewportSize({ width: 1024, height: 900 });
      await page.goto(state.path);
      await expect(page.getByText(state.text, { exact: false }).first()).toBeVisible();
      if (state.name === "degraded-no-score") {
        await expect(page.getByText("0", { exact: true })).toHaveCount(0);
      }
      if (state.name === "retryable-error") {
        await expect(page.getByRole("alert")).not.toContainText("Synthetic provider detail");
        await expect(page.getByRole("alert")).toContainText("visual-safe-request-id");
      }
      await expectNoHorizontalOverflow(page);
      await expectNoSeriousAxeViolations(page);
      await expect(page).toHaveScreenshot(`${state.name}.png`, { fullPage: true });
    });
  }

  test("reduced motion disables skeleton animation", async ({ page }) => {
    await page.goto(`/evaluations/${evaluationId}?scenario=visual-loading`);
    const animationName = await page.locator(".skeleton-line").first().evaluate(
      (element) => getComputedStyle(element).animationName,
    );
    expect(animationName).toBe("none");
  });
});
