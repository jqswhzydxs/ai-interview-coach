import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { createQueryClient } from "./api/queryClient";
import "./styles/global.css";

async function enableMocks() {
  if (import.meta.env.VITE_USE_MOCKS === "false") return;
  const { worker } = await import("./mocks/browser");
  await worker.start({
    onUnhandledFrame: ({ frame, defaults }) => {
      if (frame.protocol !== "http") return;
      const request = (frame.data as { request: Request }).request;
      if (!new URL(request.url).pathname.startsWith("/api/v1/")) return;
      defaults.error();
      throw new Error("Mock mode blocked an unmatched API request");
    },
    serviceWorker: { url: "/mockServiceWorker.js" },
  });
}

await enableMocks();

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Application root element is missing");

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={createQueryClient()}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
