import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";

import { ApiError, getAgentRunWithMeta, isMockMode } from "@/api/client";
import { DegradationNotice, ProcessingStatus, RetryPanel, Skeleton, SourceQualityBadge } from "@/components/Feedback";

export function AgentRunPage() {
  const { agentRunId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const scenario = isMockMode ? (searchParams.get("scenario") ?? "agent-running") : undefined;
  const query = useQuery({
    queryKey: ["agent-run-detail", agentRunId, scenario],
    queryFn: ({ signal }) => getAgentRunWithMeta(agentRunId, scenario, signal),
    retry: false,
    refetchInterval: (state) => {
      const result = state.state.data;
      if (!result || !["pending", "running"].includes(result.value.status)) return false;
      return result.retryAfterMs ?? Math.min(1000 * (2 ** Math.max(0, state.state.dataUpdateCount - 1)), 5000);
    },
    refetchIntervalInBackground: false,
  });
  if (query.isPending) return <Skeleton label="正在加载 Agent 运行详情" />;
  if (query.isError) {
    const error = query.error instanceof ApiError ? query.error : null;
    return (
      <RetryPanel
        title="运行详情暂时不可用"
        reason={error?.message ?? "请求未完成，请稍后重试。"}
        retryable={error?.retryable ?? false}
        requestId={error?.requestId}
        onRetry={() => void query.refetch()}
      />
    );
  }
  const run = query.data.value;
  return (
    <div className="page-stack narrow-page">
      <header>
        <p className="eyebrow">Agent Run</p>
        <h1>运行详情</h1>
        <p className="request-id">{run.agent_run_id}</p>
      </header>
      <div className="badge-row">
        <span className="badge">执行模式：{run.execution_mode}</span>
        {run.execution_mode === "fallback" ? (
          <SourceQualityBadge quality="degraded" derivedFrom="execution_mode" />
        ) : null}
      </div>
      {run.execution_mode === "fallback" ? (
        <DegradationNotice reasons={[String(run.fallback_reason?.code ?? "fallback")]} sourceQuality="degraded" />
      ) : null}
      <ProcessingStatus
        status={run.execution_mode === "fallback" ? "degraded" : run.status}
        steps={run.steps.map((step) => ({ id: step.agent_run_step_id, label: step.agent_name, status: step.status }))}
      />
      <dl className="detail-list">
        <div><dt>重试次数</dt><dd>{run.retry_count}</dd></div>
        <div><dt>真实调用次数</dt><dd>{run.real_call_count}</dd></div>
        <div><dt>延迟</dt><dd>{run.latency_ms === null ? "未知" : `${run.latency_ms} ms`}</dd></div>
      </dl>
    </div>
  );
}
