import { spawn } from "node:child_process";
import { mkdtemp, mkdir, rm } from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const frontendDirectory = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const repositoryRoot = path.dirname(frontendDirectory);
const mode = process.argv[2] ?? "all";
const updateSnapshots = process.argv.includes("--update-snapshots");
if (!["all", "real-api", "visual"].includes(mode)) {
  throw new Error("mode must be all, real-api, or visual");
}

const children = [];
let temporaryRoot;

const reservePort = () => new Promise((resolve, reject) => {
  const server = net.createServer();
  server.unref();
  server.on("error", reject);
  server.listen(0, "127.0.0.1", () => {
    const address = server.address();
    if (!address || typeof address === "string") {
      server.close();
      reject(new Error("could not reserve loopback port"));
      return;
    }
    const port = address.port;
    server.close((error) => error ? reject(error) : resolve(port));
  });
});

const spawnChild = (command, args, options = {}) => {
  const child = spawn(command, args, {
    cwd: options.cwd ?? frontendDirectory,
    env: options.env ?? process.env,
    stdio: options.stdio ?? "inherit",
    windowsHide: true,
  });
  children.push(child);
  return child;
};

const waitFor = async (url, child, label) => {
  const deadline = Date.now() + 60_000;
  let lastError;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`${label} exited with ${child.exitCode}`);
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1000) });
      if (response.ok) return;
      lastError = new Error(`${label} returned ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error(`${label} did not become ready: ${String(lastError)}`);
};

const run = (command, args, env) => new Promise((resolve, reject) => {
  const child = spawnChild(command, args, { env });
  child.on("error", reject);
  child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`${command} exited with ${code}`)));
});

const stopChildren = async () => {
  for (const child of [...children].reverse()) {
    if (child.exitCode === null) child.kill("SIGTERM");
  }
  await new Promise((resolve) => setTimeout(resolve, 300));
};

try {
  temporaryRoot = await mkdtemp(path.join(os.tmpdir(), "ai-interview-phase25c-"));
  const uploadDirectory = path.join(temporaryRoot, "uploads");
  await mkdir(uploadDirectory);
  const [apiPort, realPort, mockPort] = await Promise.all([reservePort(), reservePort(), reservePort()]);
  const apiBaseUrl = `http://127.0.0.1:${apiPort}/api/v1`;
  const realBaseUrl = `http://127.0.0.1:${realPort}`;
  const mockBaseUrl = `http://127.0.0.1:${mockPort}`;
  const python = path.join(repositoryRoot, ".venv", "Scripts", "python.exe");
  const backendEnvironment = {
    ...process.env,
    APP_ENV: "test",
    LLM_PROVIDER: "mock",
    RUN_REAL_LLM_ACCEPTANCE: "false",
    SAVE_FULL_LLM_LOGS: "false",
    DEEPSEEK_API_KEY: "",
    KIMI_API_KEY: "",
    OPENAI_API_KEY: "",
    ANTHROPIC_API_KEY: "",
    GOOGLE_API_KEY: "",
    AZURE_OPENAI_API_KEY: "",
    DATABASE_URL: `sqlite+pysqlite:///${path.join(temporaryRoot, "phase25c.db").replaceAll("\\", "/")}`,
    UPLOAD_DIR: uploadDirectory,
    CORS_ALLOWED_ORIGINS: `${realBaseUrl},${mockBaseUrl}`,
    CORS_ALLOW_CREDENTIALS: "false",
    PHASE_2_5C_API_HOST: "127.0.0.1",
    PHASE_2_5C_API_PORT: String(apiPort),
  };
  const backend = spawnChild(
    python,
    [path.join(repositoryRoot, "scripts", "run_phase_2_5c_local_backend.py")],
    { env: backendEnvironment, cwd: repositoryRoot },
  );
  await waitFor(`${apiBaseUrl}/health`, backend, "FastAPI");

  const viteCli = path.join(frontendDirectory, "node_modules", "vite", "bin", "vite.js");
  const realFrontend = spawnChild(
    process.execPath,
    [viteCli, "--host", "127.0.0.1", "--port", String(realPort), "--strictPort"],
    { env: { ...process.env, VITE_API_BASE_URL: apiBaseUrl, VITE_USE_MOCKS: "false" } },
  );
  await waitFor(realBaseUrl, realFrontend, "real-api Vite");
  const mockFrontend = spawnChild(
    process.execPath,
    [viteCli, "--host", "127.0.0.1", "--port", String(mockPort), "--strictPort"],
    { env: { ...process.env, VITE_API_BASE_URL: apiBaseUrl, VITE_USE_MOCKS: "true" } },
  );
  await waitFor(mockBaseUrl, mockFrontend, "mock Vite");

  const playwrightCli = path.join(frontendDirectory, "node_modules", "@playwright", "test", "cli.js");
  const args = [playwrightCli, "test"];
  if (mode !== "all") args.push("--project", mode);
  if (updateSnapshots) args.push("--update-snapshots");
  await run(process.execPath, args, {
    ...process.env,
    PHASE_2_5C_REAL_BASE_URL: realBaseUrl,
    PHASE_2_5C_MOCK_BASE_URL: mockBaseUrl,
  });
} finally {
  await stopChildren();
  if (temporaryRoot) {
    const resolved = path.resolve(temporaryRoot);
    const tempBase = path.resolve(os.tmpdir());
    if (!resolved.startsWith(`${tempBase}${path.sep}`) || !path.basename(resolved).startsWith("ai-interview-phase25c-")) {
      console.error("refusing to remove an unexpected directory");
      process.exitCode = 1;
    } else {
      await rm(resolved, { recursive: true, force: true });
    }
  }
}
