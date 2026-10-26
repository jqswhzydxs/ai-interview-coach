export interface MockStep {
  name: string;
  method: string;
  path: string;
  request: {
    body: unknown;
    headers: Record<string, string>;
    query: Record<string, unknown>;
  };
  response: {
    status_code: number;
    body: unknown;
  } | null;
  client_outcome: "completed" | "cancelled" | "timeout";
  ui: {
    state: string;
    retryable: boolean;
    source_quality_display?: {
      value: string;
      derived_from: string;
      label: string;
    };
    reason_message?: string;
  };
}

export interface MockScenario {
  schema_version: "frontend-mock-v0.1";
  scenario_id: string;
  category: string;
  description: string;
  data_classification: "synthetic_non_personal";
  steps: MockStep[];
}
