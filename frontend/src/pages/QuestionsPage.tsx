import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";

import { getPrepPackage, getQuestions, isMockMode } from "@/api/client";
import type { Question } from "@/api/domain";
import { DegradationNotice, EmptyState, Skeleton } from "@/components/Feedback";
import { QuestionBankTabs, QuestionCard, type QuestionModule } from "@/components/Questions";

export function QuestionsPage() {
  const { prepPackageId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const scenario = isMockMode ? (searchParams.get("scenario") ?? "standard-success") : undefined;
  const [activeModule, setActiveModule] = useState<QuestionModule>("self_intro");
  const query = useQuery({
    queryKey: ["questions", prepPackageId, scenario],
    queryFn: ({ signal }) => getQuestions(prepPackageId, scenario, signal),
  });
  const packageQuery = useQuery({
    queryKey: ["prep-package", prepPackageId],
    queryFn: ({ signal }) => getPrepPackage(prepPackageId, signal),
  });

  if (query.isPending || packageQuery.isPending) return <Skeleton count={6} label="正在加载题库" />;
  if (query.isError || packageQuery.isError) return <EmptyState title="题库暂时不可用" description="请返回进度页后重试。" />;

  const questions = query.data.items;
  const counts: Record<QuestionModule, number> = {
    self_intro: questions.filter((item) => item.module === "self_intro").length,
    professional: questions.filter((item) => item.module === "professional").length,
    behavior_project: questions.filter((item) => item.module === "behavior_project").length,
  };
  const visibleQuestions: Question[] = questions.filter((item) => item.module === activeModule);
  return (
    <div className="page-stack">
      <header>
        <p className="eyebrow">准备包 {prepPackageId}</p>
        <h1>面试题库</h1>
        <p>{packageQuery.data.title} · 共 {query.data.total} 题，按后端稳定顺序显示。</p>
      </header>
      {isMockMode && scenario === "question-bank-fallback" ? (
        <DegradationNotice reasons={["question_bank_fallback"]} sourceQuality="degraded" />
      ) : null}
      <QuestionBankTabs counts={counts} activeModule={activeModule} onChange={setActiveModule}>
        <div className="question-list">
          {visibleQuestions.map((question) => (
            <QuestionCard
              key={question.question_id}
              question={question}
              practiceHref={`/questions/${question.question_db_id}/practice`}
            />
          ))}
        </div>
      </QuestionBankTabs>
    </div>
  );
}
