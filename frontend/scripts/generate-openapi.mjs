import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

import {
  generatedPath,
  openapiCliPath,
  openapiPath,
} from "./contract-paths.mjs";

fs.mkdirSync(path.dirname(generatedPath), { recursive: true });
const result = spawnSync(
  process.execPath,
  [openapiCliPath, "--output", generatedPath, "--alphabetize"],
  {
    encoding: "utf8",
    input: fs.readFileSync(openapiPath),
    stdio: ["pipe", "inherit", "inherit"],
  },
);
if (result.status !== 0) {
  process.exit(result.status ?? 1);
}
