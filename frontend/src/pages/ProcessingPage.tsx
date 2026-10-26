import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ApiError, getAgentRunWithMeta, isMockMode } from "@/api/client";
import { DegradationNotice, ProcessingStatus, RetryPanel, Skeleton } from "@/components/Feedback";

export function ProcessingPage() {
  const { prepPackageId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const scenario = isMockMode ? (searchParams.get("scenario") ?? "agent-running") : undefined;
  const agentRunId = searchParams.get("agentRunId") ?? "";
  const query = useQuery({
    queryKey: ["agent-run", agentRunId, scenario],
    queryFn: ({ signal }) => getAgentRunWithMeta(agentRunId, scenario, signal),
    enabled: Boolean(agentRunId),
    retry: false,
    refetchInterval: (state) => {
      const result = state.state.data;
      if (!result || !["pending", "running"].includes(result.value.status)) return false;
      return result.retryAfterMs ?? Math.min(1000 * (2 ** Math.max(0, state.state.dataUpdateCount - 1)), 5000);
    },
    refetchIntervalInBackground: false,
  });
  if (!agentRunId) {
    return (
      <RetryPanel
        title="缺少运行记录标识"
        reason="请从刚创建的准备任务进入此页面。"
        retryable={false}
      />
    );
  }

  if (query.isPending) return <Skeleton label="正在加载处理状态" />;
  if (query.isError) {
    const error = query.error instanceof ApiError ? query.error : null;
    return (
      <RetryPanel
        title="无法获取处理状态"
        reason={error?.message ?? "请求未完成，请稍后重试。"}
        retryable={error?.retryable ?? false}
        requestId={error?.requestId}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const run = query.data.value;
  const displayStatus = run.execution_mode === "fallback" ? "degraded" : run.status;
  return (
    <div className="page-stack narrow-page">
      <header>
        <p className="eyebrow">准备包 {prepPackageId}</p>
        <h1>生成进度</h1>
        <p>页面只展示当前状态，不会自动触发下一阶段请求。</p>
      </header>
      {run.execution_mode === "fallback" ? (
        <DegradationNotice reasons={[String(run.fallback_reason?.code ?? "fallback")]} sourceQuality="degraded" />
      ) : null}
      <ProcessingStatus
        status={displayStatus}
        steps={run.steps.map((step) => ({ id: step.agent_run_step_id, label: step.agent_name, status: step.status }))}
        agentRunHref={`/agent-runs/${run.agent_run_id}${scenario ? `?scenario=${scenario}` : ""}`}
      />
      <div className="button-row">
        <Link className="button-link" to={`/prep/${prepPackageId}/questions`}>查看题库</Link>
        <Link className="secondary-link" to="/">返回首页</Link>
      </div>
    </div>
  );
}
