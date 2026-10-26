import { AlertCircle, CheckCircle2, Clock3, Info, RefreshCw } from "lucide-react";
import { Component, type ReactNode } from "react";
import { Link } from "react-router-dom";

import type { EvaluationMode, SourceQuality } from "@/api/domain";

const sourceLabels: Record<SourceQuality, string> = {
  trusted: "可信来源",
  synthetic: "合成来源",
  degraded: "降级来源",
  user_provided: "用户提供",
  mixed: "混合来源",
  unknown: "来源未知",
};

const reasonLabels: Record<string, string> = {
  "upstream_fallback:question": "题目来源暂时降级。",
  evaluator_fallback: "评价服务暂时无法提供可信分数。",
  upstream_profile_fallback: "上游画像暂时不可用，当前结果使用了安全降级来源。",
  question_bank_fallback: "题库生成使用了安全 fallback。",
};

export function SourceQualityBadge({
  quality,
  derivedFrom,
}: {
  quality: SourceQuality;
  derivedFrom?: string;
}) {
  return (
    <span className={`badge badge-${quality}`} title={derivedFrom ? `来源：${derivedFrom}` : undefined}>
      <Info aria-hidden="true" size={15} />
      {sourceLabels[quality]}
    </span>
  );
}

export function EvaluationModeBadge({ mode }: { mode: EvaluationMode }) {
  return (
    <span className={`badge badge-${mode}`}>
      {mode === "degraded" ? <AlertCircle aria-hidden="true" size={15} /> : <CheckCircle2 aria-hidden="true" size={15} />}
      {mode === "degraded" ? "降级评价" : "标准评价"}
    </span>
  );
}

export function DegradationNotice({
  reasons,
  sourceQuality,
  children,
}: {
  reasons: string[];
  sourceQuality: SourceQuality;
  children?: ReactNode;
}) {
  return (
    <section className="notice notice-degraded" aria-labelledby="degradation-title">
      <div className="notice-heading">
        <AlertCircle aria-hidden="true" />
        <h2 id="degradation-title">当前结果已降级</h2>
      </div>
      <SourceQualityBadge quality={sourceQuality} />
      <ul>
        {reasons.map((reason) => (
          <li key={reason}>{reasonLabels[reason] ?? "部分来源暂时不可用，结果已按安全规则降级。"}</li>
        ))}
      </ul>
      {children}
    </section>
  );
}

export function NoScoreState({
  reason = "评价来源不足以支持精确评分。",
  sourceQuality,
}: {
  reason?: string;
  sourceQuality: SourceQuality;
}) {
  return (
    <section className="no-score-state" aria-labelledby="no-score-title">
      <AlertCircle aria-hidden="true" />
      <div>
        <h2 id="no-score-title">本次无法提供可信分数</h2>
        <p>{reason}</p>
        <SourceQualityBadge quality={sourceQuality} />
      </div>
    </section>
  );
}

export function ScoreCard({
  score,
  maxScore = 100,
  scoreAvailable,
  sourceQuality,
}: {
  score: number | null;
  maxScore?: number;
  scoreAvailable: boolean;
  sourceQuality: SourceQuality;
}) {
  if (!scoreAvailable || score === null) {
    return <NoScoreState sourceQuality={sourceQuality} />;
  }
  return (
    <section className="score-card" aria-label="总分">
      <span className="score-value">{score}</span>
      <span className="score-maximum">/ {maxScore}</span>
    </section>
  );
}

export interface ProcessingStep {
  id: string;
  label: string;
  status: "pending" | "running" | "succeeded" | "failed";
}

export function ProcessingStatus({
  status,
  steps,
  agentRunHref,
}: {
  status: "pending" | "running" | "succeeded" | "failed" | "degraded" | "cancelled";
  steps: ProcessingStep[];
  agentRunHref?: string;
}) {
  return (
    <section className="processing-status" role="status" aria-live="polite" aria-atomic="true">
      <div className="notice-heading">
        <Clock3 aria-hidden="true" />
        <h2>{status === "running" ? "正在生成准备包" : `任务状态：${status}`}</h2>
      </div>
      <ol>
        {steps.map((step) => (
          <li key={step.id}>
            <span className={`status-dot status-${step.status}`} aria-hidden="true" />
            {step.label}：{step.status}
          </li>
        ))}
      </ol>
      {agentRunHref ? <Link to={agentRunHref}>查看 Agent 运行详情</Link> : null}
    </section>
  );
}

export function RetryPanel({
  title,
  reason,
  retryable,
  requestId,
  onRetry,
  onEdit,
}: {
  title: string;
  reason: string;
  retryable: boolean;
  requestId?: string | null | undefined;
  onRetry?: (() => void) | undefined;
  onEdit?: (() => void) | undefined;
}) {
  return (
    <section className="notice notice-error" role="alert" aria-labelledby="retry-title" tabIndex={-1}>
      <div className="notice-heading">
        <AlertCircle aria-hidden="true" />
        <h2 id="retry-title">{title}</h2>
      </div>
      <p>{reason}</p>
      {requestId ? <p className="request-id">请求 ID：{requestId}</p> : null}
      <div className="button-row">
        {retryable && onRetry ? (
          <button type="button" onClick={onRetry}>
            <RefreshCw aria-hidden="true" size={18} /> 重试
          </button>
        ) : null}
        {onEdit ? <button type="button" className="secondary-button" onClick={onEdit}>返回修改</button> : null}
      </div>
    </section>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <section className="empty-state">
      <Info aria-hidden="true" />
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </section>
  );
}

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch() {
    // Intentionally no console logging: error bodies and user content are sensitive.
  }

  render() {
    if (this.state.hasError) {
      return (
        <section className="notice notice-error" role="alert">
          <h1>页面暂时无法显示</h1>
          <p>请返回首页后重试。错误详情未写入浏览器日志。</p>
          <a href="/">返回首页</a>
        </section>
      );
    }
    return this.props.children;
  }
}

export function Skeleton({ count = 3, label = "正在加载" }: { count?: number; label?: string }) {
  return (
    <div className="skeleton-container" role="status" aria-label={label}>
      <span className="visually-hidden">{label}</span>
      <div aria-hidden="true">
        {Array.from({ length: count }, (_, index) => (
          <div className="skeleton-line" key={index} />
        ))}
      </div>
    </div>
  );
}
