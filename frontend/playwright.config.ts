import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "@playwright/test";

const projectDirectory = path.dirname(fileURLToPath(import.meta.url));
const chromeExecutable = process.env.PHASE_2_5C_CHROMIUM_PATH
  ?? "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results/phase-2.5c",
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  timeout: 120_000,
  expect: { timeout: 10_000, toHaveScreenshot: { animations: "disabled", caret: "hide" } },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  use: {
    browserName: "chromium",
    launchOptions: { executablePath: chromeExecutable },
    locale: "zh-CN",
    timezoneId: "Asia/Singapore",
    colorScheme: "light",
    contextOptions: { reducedMotion: "reduce" },
    serviceWorkers: "allow",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  snapshotPathTemplate: path.join(
    projectDirectory,
    "e2e",
    "__screenshots__",
    "{projectName}",
    "{arg}{ext}",
  ),
  projects: [
    {
      name: "real-api",
      testMatch: /real-api\.spec\.ts/u,
      use: { baseURL: process.env.PHASE_2_5C_REAL_BASE_URL ?? "http://127.0.0.1:14173" },
    },
    {
      name: "visual",
      testMatch: /visual\.spec\.ts/u,
      use: { baseURL: process.env.PHASE_2_5C_MOCK_BASE_URL ?? "http://127.0.0.1:14174" },
    },
  ],
});
