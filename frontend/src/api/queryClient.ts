import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./client";

export const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) =>
          error instanceof ApiError && error.retryable && failureCount < 1,
        retryDelay: (failureCount, error) =>
          error instanceof ApiError && error.retryAfterMs !== null
            ? error.retryAfterMs
            : Math.min(500 * (2 ** failureCount), 5000),
      },
      mutations: {
        retry: false,
      },
    },
  });
