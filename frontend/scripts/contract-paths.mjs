import path from "node:path";
import { fileURLToPath } from "node:url";

export const frontendRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
export const repositoryRoot = path.resolve(frontendRoot, "..");
export const contractRoot = path.resolve(
  repositoryRoot,
  "contracts/frontend/phase-2.5a-v0.1",
);
export const openapiPath = path.resolve(contractRoot, "openapi.json");
export const manifestPath = path.resolve(contractRoot, "contract-manifest.json");
export const catalogPath = path.resolve(contractRoot, "mock-scenario-catalog.json");
export const generatedPath = path.resolve(
  frontendRoot,
  "src/api/generated/openapi.ts",
);
export const openapiCliPath = path.resolve(
  frontendRoot,
  "node_modules/openapi-typescript/bin/cli.js",
);
