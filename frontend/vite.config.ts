import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const projectDirectory = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(projectDirectory, "src"),
      "@phase25a": path.resolve(
        projectDirectory,
        "../contracts/frontend/phase-2.5a-v0.1",
      ),
    },
  },
  server: {
    fs: {
      allow: [projectDirectory, path.resolve(projectDirectory, "../contracts")],
    },
  },
  test: {
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
    environment: "jsdom",
    environmentOptions: { jsdom: { url: "http://localhost/" } },
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    restoreMocks: true,
  },
});
