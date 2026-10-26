import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";

import { ApiError, getEvaluation, isMockMode } from "@/api/client";
import { DegradationNotice, EvaluationModeBadge, RetryPanel, ScoreCard, Skeleton, SourceQualityBadge } from "@/components/Feedback";
import { EvaluationDimensions } from "@/components/Questions";

export function EvaluationPage() {
  const { evaluationId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const scenario = isMockMode ? (searchParams.get("scenario") ?? "standard-evaluation") : undefined;
  const query = useQuery({
    queryKey: ["evaluation", evaluationId, scenario],
    queryFn: ({ signal }) => getEvaluation(evaluationId, scenario, signal),
    retry: false,
  });

  if (query.isPending) return <Skeleton count={5} label="正在加载评价结果" />;
  if (query.isError) {
    const error = query.error instanceof ApiError ? query.error : null;
    return (
      <RetryPanel
        title="评价结果暂时不可用"
        reason={error?.message ?? "请求未完成，请稍后重试。"}
        retryable={error?.retryable ?? false}
        requestId={error?.requestId}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const data = query.data;
  const memoryBlocked = data.memory_update.write_decision === "skip";
  return (
    <div className="page-stack narrow-page">
      <header>
        <p className="eyebrow">评价结果</p>
        <h1>本次回答反馈</h1>
        <div className="badge-row">
          <EvaluationModeBadge mode={data.evaluation_mode} />
          <SourceQualityBadge quality={data.source_quality} />
        </div>
      </header>
      {data.evaluation_mode === "degraded" ? (
        <DegradationNotice reasons={data.degradation_reasons} sourceQuality={data.source_quality} />
      ) : null}
      <ScoreCard
        score={data.total_score}
        scoreAvailable={data.score_available}
        sourceQuality={data.source_quality}
      />
      <EvaluationDimensions
        items={data.evaluation.dimension_scores}
        scoreAvailable={data.score_available}
      />
      {memoryBlocked ? (
        <section className="notice notice-info" aria-labelledby="memory-status-title">
          <h2 id="memory-status-title">本次结果未写入长期记忆</h2>
          <p>这是来源安全保护，不表示系统失败，也不表示你的回答已丢失。</p>
        </section>
      ) : null}
      <section>
        <h2>改进建议</h2>
        <ul>{data.improvement_points.map((item) => <li key={item}>{item}</li>)}</ul>
        <h3>参考改写</h3>
        <p>{data.improved_answer}</p>
      </section>
    </div>
  );
}
