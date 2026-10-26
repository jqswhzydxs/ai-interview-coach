import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

import {
  generatedPath,
  manifestPath,
  openapiCliPath,
  openapiPath,
} from "./contract-paths.mjs";

const sha256 = (filePath) =>
  crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
const actualOpenapiHash = sha256(openapiPath);
if (actualOpenapiHash !== manifest.openapi.sha256) {
  throw new Error(
    `OpenAPI SHA-256 drift: expected ${manifest.openapi.sha256}, got ${actualOpenapiHash}`,
  );
}
if (!fs.existsSync(generatedPath)) {
  throw new Error("generated OpenAPI types are missing; run npm run contract:generate");
}

const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "phase-2-5b-openapi-"));
const temporaryOutput = path.join(temporaryDirectory, "openapi.ts");
try {
  const generation = spawnSync(
    process.execPath,
    [openapiCliPath, "--output", temporaryOutput, "--alphabetize"],
    {
      encoding: "utf8",
      input: fs.readFileSync(openapiPath),
      stdio: "pipe",
    },
  );
  if (generation.status !== 0) {
    process.stderr.write(generation.stderr);
    process.exit(generation.status ?? 1);
  }
  if (!fs.readFileSync(generatedPath).equals(fs.readFileSync(temporaryOutput))) {
    throw new Error(
      "generated OpenAPI types differ from the frozen contract; run npm run contract:generate",
    );
  }
} finally {
  fs.rmSync(temporaryDirectory, { recursive: true, force: true });
}

const mockCheck = spawnSync(process.execPath, [path.resolve("scripts/check-mocks.mjs")], {
  encoding: "utf8",
  stdio: "inherit",
});
if (mockCheck.status !== 0) process.exit(mockCheck.status ?? 1);

console.log(`contract_check=passed openapi_sha256=${actualOpenapiHash}`);
