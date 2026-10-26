import agentRunning from "@phase25a/mocks/agent-running.json";
import emptyHistory from "@phase25a/mocks/empty-history.json";
import evaluatorDegraded from "@phase25a/mocks/evaluator-degraded.json";
import fileUploadFailure from "@phase25a/mocks/file-upload-failure.json";
import memoryWriteBlocked from "@phase25a/mocks/memory-write-blocked.json";
import nonretryableContractError from "@phase25a/mocks/nonretryable-contract-error.json";
import questionBankFallback from "@phase25a/mocks/question-bank-fallback.json";
import requestCancelledTimeout from "@phase25a/mocks/request-cancelled-timeout.json";
import retryableProviderError from "@phase25a/mocks/retryable-provider-error.json";
import standardEvaluation from "@phase25a/mocks/standard-evaluation.json";
import standardSuccess from "@phase25a/mocks/standard-success.json";
import upstreamFallback from "@phase25a/mocks/upstream-fallback.json";

import type { MockScenario } from "./types";

const scenarioValues = [
  agentRunning,
  emptyHistory,
  evaluatorDegraded,
  fileUploadFailure,
  memoryWriteBlocked,
  nonretryableContractError,
  questionBankFallback,
  requestCancelledTimeout,
  retryableProviderError,
  standardEvaluation,
  standardSuccess,
  upstreamFallback,
] as unknown as MockScenario[];

export const mockScenarios = Object.fromEntries(
  scenarioValues.map((scenario) => [scenario.scenario_id, scenario]),
) as Record<string, MockScenario>;

export const mockScenarioIds = scenarioValues.map((scenario) => scenario.scenario_id);
