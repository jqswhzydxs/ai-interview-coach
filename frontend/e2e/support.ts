import path from "node:path";

import type { Page, TestInfo } from "@playwright/test";

const loopbackHosts = new Set(["127.0.0.1", "localhost", "::1"]);

export async function enforceLoopbackOnly(page: Page): Promise<string[]> {
  const blocked: string[] = [];
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (["about:", "blob:", "data:"].includes(url.protocol) || loopbackHosts.has(url.hostname)) {
      await route.continue();
      return;
    }
    blocked.push(`${url.protocol}//${url.host}`);
    await route.abort("blockedbyclient");
  });
  return blocked;
}

export async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  if (hasOverflow) throw new Error("horizontal overflow detected");
}

export async function expectMinimumTargets(page: Page): Promise<void> {
  const undersized = await page.locator("a:visible, button:visible, input:visible, textarea:visible").evaluateAll(
    (elements) => elements
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return { name: element.getAttribute("aria-label") ?? element.textContent?.trim(), width: rect.width, height: rect.height };
      })
      .filter((value) => value.width < 44 || value.height < 44),
  );
  if (undersized.length > 0) throw new Error(`undersized targets: ${JSON.stringify(undersized)}`);
}

export async function expectNoSeriousAxeViolations(page: Page): Promise<void> {
  await page.addScriptTag({ path: path.resolve("node_modules/axe-core/axe.min.js") });
  const violations = await page.evaluate(async () => {
    const axe = (window as unknown as { axe: { run: () => Promise<{ violations: Array<{ id: string; impact: string | null }> }> } }).axe;
    const result = await axe.run();
    return result.violations.filter((item) => item.impact === "serious" || item.impact === "critical");
  });
  if (violations.length > 0) throw new Error(`axe violations: ${JSON.stringify(violations)}`);
}

export function screenshotName(testInfo: TestInfo, suffix: string): string {
  return `${testInfo.project.name}-${suffix}`.replace(/[^a-z0-9-]+/giu, "-").toLowerCase();
}
