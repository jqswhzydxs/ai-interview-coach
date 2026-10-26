import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { ApiError, createEvaluation, isMockMode } from "@/api/client";
import { questionSchema } from "@/api/domain";
import { ProcessingStatus, RetryPanel } from "@/components/Feedback";
import { AnswerEditor } from "@/components/Questions";

const isAbortError = (value: unknown): boolean =>
  value instanceof DOMException && ["AbortError", "TimeoutError"].includes(value.name);

export function PracticePage() {
  const { questionId = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState<string>();
  const [cancelled, setCancelled] = useState(false);
  const submitLocked = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);
  const parsedQuestion = questionSchema.safeParse(
    (location.state as { question?: unknown } | null)?.question,
  );
  const question = parsedQuestion.success ? parsedQuestion.data : null;

  useEffect(() => () => controllerRef.current?.abort(), []);

  useEffect(() => {
    if (!answer.trim()) return undefined;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [answer]);

  const mutation = useMutation({
    retry: false,
    mutationFn: async () => {
      const controller = new AbortController();
      controllerRef.current = controller;
      setCancelled(false);
      return createEvaluation(
        { question_db_id: questionId, custom_question_text: null, user_answer: answer.trim() },
        undefined,
        controller.signal,
      );
    },
    onSuccess: (result) => {
      const suffix = isMockMode ? "?scenario=standard-evaluation" : "";
      navigate(`/evaluations/${result.answer_evaluation_id}${suffix}`, {
        state: { agentRunId: result.agent_run_id },
      });
    },
    onError: (value) => {
      if (isAbortError(value)) setCancelled(true);
    },
    onSettled: () => {
      submitLocked.current = false;
      controllerRef.current = null;
    },
  });

  const submit = () => {
    if (submitLocked.current || mutation.isPending) return;
    if (answer.trim().length < 10) {
      setError("请至少输入 10 个字符后再提交。");
      return;
    }
    submitLocked.current = true;
    mutation.mutate();
  };
  const apiError = mutation.error instanceof ApiError ? mutation.error : null;

  return (
    <div className="page-stack narrow-page">
      <header>
        <p className="eyebrow">题目 {question?.question_id ?? questionId}</p>
        <h1>单题练习</h1>
        <p>{question?.question_text ?? "请围绕背景、约束、选择和结果组织回答。"}</p>
      </header>
      {mutation.isPending ? (
        <>
          <ProcessingStatus
            status="running"
            steps={[{
              id: "evaluation",
              label: "同步等待评价完成",
              status: "running",
            }]}
          />
          <p>当前接口同步执行；取消只终止当前浏览器请求，不会自动重新提交。</p>
          <button type="button" className="secondary-button" onClick={() => controllerRef.current?.abort()}>
            取消本次评价请求
          </button>
        </>
      ) : (
        <AnswerEditor
          value={answer}
          error={error}
          disabled={mutation.isPending}
          onChange={(value) => {
            setAnswer(value);
            setError(undefined);
          }}
          onSubmit={submit}
        />
      )}
      {mutation.isError ? (
        <RetryPanel
          title={cancelled ? "本次评价请求已取消" : "评价请求未完成"}
          reason={cancelled ? "回答仍保留在当前页面，可修改后重新提交。" : (apiError?.message ?? "请求未完成，请稍后重试。")}
          retryable={!cancelled && (apiError?.retryable ?? false)}
          requestId={apiError?.requestId}
          onRetry={submit}
        />
      ) : null}
    </div>
  );
}
