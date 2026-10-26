import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderRoute } from "./render";

const evaluationId = "00000000-0000-4000-8000-000000000601";

describe("evaluation contract rendering", () => {
  it("shows standard total score, dimension scores and suggestions", async () => {
    renderRoute(`/evaluations/${evaluationId}`);
    expect(await screen.findByRole("heading", { name: "本次回答反馈" })).toBeVisible();
    expect(screen.getByLabelText("总分")).toBeVisible();
    expect(screen.getByRole("heading", { name: "维度评分" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "改进建议" })).toBeVisible();
  });

  it("never renders a zero or dimension score for degraded no-score results", async () => {
    renderRoute(`/evaluations/${evaluationId}?scenario=evaluator-degraded`);
    expect(await screen.findByRole("heading", { name: "本次无法提供可信分数" })).toBeVisible();
    expect(screen.getByText("降级评价")).toBeVisible();
    expect(screen.getAllByText("降级来源").length).toBeGreaterThan(0);
    expect(screen.queryByLabelText("总分")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "维度评分" })).not.toBeInTheDocument();
    expect(screen.queryByText(/^0(?:\s*\/|分)/u)).not.toBeInTheDocument();
  });

  it("explains a memory-write block as a safety outcome", async () => {
    renderRoute(`/evaluations/${evaluationId}?scenario=memory-write-blocked`);
    expect(await screen.findByRole("heading", { name: "本次结果未写入长期记忆" })).toBeVisible();
    expect(screen.getByText(/不表示系统失败/u)).toBeVisible();
    expect(screen.getByText(/不表示你的回答已丢失/u)).toBeVisible();
  });
});
