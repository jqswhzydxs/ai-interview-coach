import { useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { ArrowRight, Send } from "lucide-react";
import { Link } from "react-router-dom";

import type { Question, ScoreItem } from "@/api/domain";

export type QuestionModule = Question["module"];

const moduleLabels: Record<QuestionModule, string> = {
  self_intro: "自我介绍",
  professional: "专业问题",
  behavior_project: "行为与项目",
};

export function QuestionBankTabs({
  counts,
  activeModule,
  onChange,
  children,
}: {
  counts: Record<QuestionModule, number>;
  activeModule: QuestionModule;
  onChange: (module: QuestionModule) => void;
  children: ReactNode;
}) {
  const modules = Object.keys(moduleLabels) as QuestionModule[];
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const next = modules[(index + direction + modules.length) % modules.length];
    if (next) {
      onChange(next);
      refs.current[next]?.focus();
    }
  };
  return (
    <div>
      <div className="question-tabs" role="tablist" aria-label="题库模块">
        {modules.map((module, index) => (
          <button
            key={module}
            ref={(element) => { refs.current[module] = element; }}
            id={`tab-${module}`}
            type="button"
            role="tab"
            aria-selected={activeModule === module}
            aria-controls={`panel-${module}`}
            tabIndex={activeModule === module ? 0 : -1}
            onClick={() => onChange(module)}
            onKeyDown={(event) => onKeyDown(event, index)}
          >
            {moduleLabels[module]} <span>({counts[module]})</span>
          </button>
        ))}
      </div>
      <section
        id={`panel-${activeModule}`}
        role="tabpanel"
        aria-labelledby={`tab-${activeModule}`}
        tabIndex={0}
      >
        {children}
      </section>
    </div>
  );
}

export function QuestionCard({
  question,
  practiceHref,
}: {
  question: Question;
  practiceHref: string;
}) {
  return (
    <article className="question-card">
      <div className="card-meta">
        <span>{moduleLabels[question.module]}</span>
        <span>难度：{question.difficulty}</span>
        <span>来源：{question.source_type}</span>
      </div>
      <h2>{question.sort_order}. {question.question_text}</h2>
      <p>{question.purpose}</p>
      <Link className="button-link" to={practiceHref} state={{ question }}>
        开始练习 <ArrowRight aria-hidden="true" size={18} />
      </Link>
    </article>
  );
}

export function AnswerEditor({
  value,
  error,
  disabled,
  onChange,
  onSubmit,
}: {
  value: string;
  error?: string | undefined;
  disabled?: boolean | undefined;
  onChange: (value: string) => void;
  onSubmit: () => void;
}) {
  const editorRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (error) editorRef.current?.focus();
  }, [error]);
  return (
    <div className="field-group">
      <label htmlFor="answer-editor">你的回答</label>
      <p id="answer-helper" className="field-helper">回答只保存在当前页面内存，提交前可随时修改。</p>
      <textarea
        ref={editorRef}
        id="answer-editor"
        rows={12}
        value={value}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={`answer-helper${error ? " answer-error" : ""}`}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? <p id="answer-error" className="field-error">{error}</p> : null}
      <button type="button" onClick={onSubmit} disabled={disabled}>
        <Send aria-hidden="true" size={18} />
        {disabled ? "正在提交" : "提交回答"}
      </button>
    </div>
  );
}

export function EvaluationDimensions({
  items,
  scoreAvailable,
}: {
  items: ScoreItem[];
  scoreAvailable: boolean;
}) {
  if (!scoreAvailable) return null;
  return (
    <section aria-labelledby="dimension-title">
      <h2 id="dimension-title">维度评分</h2>
      <div className="dimension-list">
        {items.map((item) => (
          <article key={item.name} className="dimension-item">
            <div>
              <h3>{item.name}</h3>
              <p>{item.reason}</p>
            </div>
            <strong aria-label={`${item.name} ${item.score} 分，满分 ${item.max_score} 分`}>
              {item.score} / {item.max_score}
            </strong>
          </article>
        ))}
      </div>
    </section>
  );
}
