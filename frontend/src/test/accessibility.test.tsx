import axe from "axe-core";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderRoute } from "./render";

describe("critical-page accessibility", () => {
  it.each([
    ["home", "/", "把面试准备拆成可执行的练习"],
    ["new preparation", "/prep/new", "提供本次练习所需资料"],
    ["degraded evaluation", "/evaluations/00000000-0000-4000-8000-000000000601?scenario=evaluator-degraded", "本次回答反馈"],
  ])("has no serious or critical axe violations: %s", async (_name, path, heading) => {
    const { container } = renderRoute(path);
    expect(await screen.findByRole("heading", { name: heading })).toBeVisible();
    const result = await axe.run(container, {
      resultTypes: ["violations"],
      rules: { "color-contrast": { enabled: false } },
    });
    expect(result.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
  });
});
