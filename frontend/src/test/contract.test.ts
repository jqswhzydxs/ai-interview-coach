import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import manifest from "@phase25a/contract-manifest.json";
import { describe, expect, it } from "vitest";

import { mockScenarioIds, mockScenarios } from "@/mocks/scenarios";

describe("frozen Phase 2.5A contract", () => {
  it("matches the preregistered OpenAPI SHA-256", () => {
    const openApiPath = resolve("../contracts/frontend/phase-2.5a-v0.1/openapi.json");
    const digest = createHash("sha256").update(readFileSync(openApiPath)).digest("hex");
    expect(digest).toBe(manifest.openapi.sha256);
    expect(digest).toBe("e983971aec77ddaf246efbb80637134f4fd41bfb9302fa2f3d06122430977304");
  });

  it("loads all 12 synthetic scenarios without sensitive payload classes", () => {
    expect(mockScenarioIds).toHaveLength(12);
    expect(new Set(mockScenarioIds).size).toBe(12);
    for (const scenario of Object.values(mockScenarios)) {
      expect(scenario.data_classification).toBe("synthetic_non_personal");
      expect(scenario.steps.length).toBeGreaterThan(0);
      expect(JSON.stringify(scenario)).not.toMatch(/api[_-]?key|authorization|reasoning_content|traceback/iu);
    }
  });

  it("keeps the degraded score contract nullable instead of zero-filled", () => {
    const step = mockScenarios["evaluator-degraded"]?.steps[0];
    expect(step?.response).not.toBeNull();
    const body = step?.response?.body as {
      data: { score_available: boolean; total_score: number | null; evaluation: { dimension_scores: unknown[] } };
    };
    expect(body.data.score_available).toBe(false);
    expect(body.data.total_score).toBeNull();
    expect(body.data.evaluation.dimension_scores).toEqual([]);
  });
});
