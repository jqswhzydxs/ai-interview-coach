import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import {
  catalogPath,
  contractRoot,
  manifestPath,
  repositoryRoot,
} from "./contract-paths.mjs";

const readJson = (filePath) => JSON.parse(fs.readFileSync(filePath, "utf8"));
const sha256 = (filePath) =>
  crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

const manifest = readJson(manifestPath);
const catalog = readJson(catalogPath);
assert(catalog.scenario_count === 12, "Phase 2.5A must contain 12 mock scenarios");
assert(manifest.mock_contract.scenario_count === 12, "manifest mock count drift");

const scenarios = new Map();
for (const entry of catalog.scenarios) {
  const fixturePath = path.resolve(contractRoot, entry.file);
  const repositoryRelative = path
    .relative(repositoryRoot, fixturePath)
    .replaceAll(path.sep, "/");
  assert(
    manifest.mock_contract.files[repositoryRelative] === sha256(fixturePath),
    `mock hash drift: ${entry.scenario_id}`,
  );
  const fixture = readJson(fixturePath);
  assert(fixture.schema_version === "frontend-mock-v0.1", "mock schema drift");
  assert(
    fixture.data_classification === "synthetic_non_personal",
    "mock data classification drift",
  );
  assert(fixture.steps.length > 0, `empty scenario: ${entry.scenario_id}`);
  scenarios.set(entry.scenario_id, fixture);
}

const degraded = scenarios
  .get("evaluator-degraded")
  .steps[0].response.body.data.evaluation;
assert(degraded.evaluation_mode === "degraded", "degraded mode drift");
assert(degraded.score_available === false, "degraded score availability drift");
assert(degraded.total_score === null, "degraded score must remain null");
assert(degraded.dimension_scores.length === 0, "degraded dimensions must be empty");

const standard = scenarios
  .get("standard-evaluation")
  .steps[0].response.body.data.evaluation;
assert(standard.evaluation_mode === "standard", "standard mode drift");
assert(standard.score_available === true, "standard score must be available");
assert(typeof standard.total_score === "number", "standard score must be numeric");
assert(standard.dimension_scores.length > 0, "standard dimensions required");

const memory = scenarios
  .get("memory-write-blocked")
  .steps[0].response.body.data.memory_update;
assert(memory.write_decision === "skip", "memory no-write contract drift");

for (const id of ["upstream-fallback", "question-bank-fallback"]) {
  const runStep = scenarios
    .get(id)
    .steps.find((step) => step.response?.body?.data?.execution_mode);
  assert(runStep.response.body.data.execution_mode === "fallback", `${id} mode drift`);
  assert(runStep.response.body.data.fallback_reason, `${id} reason missing`);
  assert(
    runStep.ui.source_quality_display.value === "degraded",
    `${id} source quality missing`,
  );
}

const questions = scenarios
  .get("standard-success")
  .steps.find((step) => step.response?.body?.data?.total === 25).response.body.data.items;
assert(questions.length === 25, "question count drift");
assert(questions.filter((item) => item.module === "self_intro").length === 8, "self intro count drift");
assert(questions.filter((item) => item.module === "professional").length === 8, "professional count drift");
assert(questions.filter((item) => item.module === "behavior_project").length === 9, "behavior count drift");

const serialized = JSON.stringify([...scenarios.values()]).toLowerCase();
for (const marker of [
  "api_key",
  "authorization: bearer",
  "raw_response",
  "reasoning_content",
  "chain_of_thought",
  "begin private key",
  "question_bank_draft_agent_v0.3",
]) {
  assert(!serialized.includes(marker), `forbidden mock marker: ${marker}`);
}

console.log(`mock_contract=passed scenarios=${scenarios.size}`);
