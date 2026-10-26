import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Controller, useForm, type Resolver } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import {
  ApiError,
  createExperience,
  createJob,
  createPrepPackage,
  createResume,
  createTextDocument,
  isMockMode,
  parseExperience,
  parseJob,
  parseResume,
  uploadDocument,
} from "@/api/client";
import { RetryPanel, ProcessingStatus } from "@/components/Feedback";
import { ExperienceInput, JobInput, ResumeInput, UploadDropzone } from "@/components/FormInputs";
import { Stepper, type StepDefinition } from "@/components/Stepper";

const maxUploadBytes = 10 * 1024 * 1024;
const allowedUploadExtensions = [".pdf", ".docx", ".txt"];

const formSchema = z.object({
  resume: z.string(),
  job: z.string().trim().min(10, "请至少输入 10 个字符的职位描述。"),
  experience: z.string(),
});

type FormValues = z.infer<typeof formSchema>;
type SubmissionStage = "idle" | "documents" | "profiles" | "parsing" | "package";

const resolver: Resolver<FormValues> = async (values) => {
  const result = formSchema.safeParse(values);
  if (result.success) return { values: result.data, errors: {} };
  return {
    values: {},
    errors: Object.fromEntries(
      result.error.issues.map((issue) => [
        String(issue.path[0]),
        { type: issue.code, message: issue.message },
      ]),
    ),
  };
};

const steps: StepDefinition[] = [
  { id: "resume", label: "简历", description: "上传或粘贴" },
  { id: "job", label: "JD", description: "目标职位" },
  { id: "experience", label: "面经", description: "可选" },
  { id: "review", label: "确认", description: "检查并提交" },
];

const submissionSteps = (stage: SubmissionStage) => {
  const ids: SubmissionStage[] = ["documents", "profiles", "parsing", "package"];
  const labels: Record<Exclude<SubmissionStage, "idle">, string> = {
    documents: "保存本次资料",
    profiles: "创建简历、JD 与可选面经记录",
    parsing: "等待 mock Agent 同步解析",
    package: "等待准备包和题库同步生成",
  };
  const activeIndex = ids.indexOf(stage);
  return ids.map((id, index) => ({
    id,
    label: labels[id as Exclude<SubmissionStage, "idle">],
    status: index < activeIndex ? "succeeded" as const : index === activeIndex ? "running" as const : "pending" as const,
  }));
};

const isAbortError = (value: unknown): boolean =>
  value instanceof DOMException && ["AbortError", "TimeoutError"].includes(value.name);

export function PrepNewPage() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState("resume");
  const [completed, setCompleted] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string>();
  const [submissionStage, setSubmissionStage] = useState<SubmissionStage>("idle");
  const [cancelled, setCancelled] = useState(false);
  const [submissionLocked, setSubmissionLocked] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const errorSummaryRef = useRef<HTMLDivElement>(null);
  const {
    control,
    handleSubmit,
    trigger,
    getValues,
    setError,
    clearErrors,
    formState: { errors, isDirty },
  } = useForm<FormValues>({
    defaultValues: { resume: "", job: "", experience: "" },
    resolver,
    mode: "onBlur",
  });

  useEffect(() => () => controllerRef.current?.abort(), []);

  useEffect(() => {
    if (!isDirty) return undefined;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const warnOnLink = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target.closest("a") : null;
      if (target instanceof HTMLAnchorElement && !window.confirm("尚有未提交的敏感内容，确定离开吗？")) {
        event.preventDefault();
      }
    };
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", warnOnLink, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", warnOnLink, true);
    };
  }, [isDirty]);

  const mutation = useMutation({
    retry: false,
    mutationFn: async (values: FormValues) => {
      const controller = new AbortController();
      controllerRef.current = controller;
      const signal = controller.signal;
      setCancelled(false);

      setSubmissionStage("documents");
      const resumeDocument = file
        ? await uploadDocument("resume", file, signal)
        : await createTextDocument({ document_type: "resume", raw_text: values.resume.trim() }, signal);
      const jobDocument = await createTextDocument(
        { document_type: "jd", raw_text: values.job.trim() },
        signal,
      );
      const experienceDocument = values.experience.trim()
        ? await createTextDocument(
            { document_type: "interview_experience", raw_text: values.experience.trim() },
            signal,
          )
        : null;

      setSubmissionStage("profiles");
      const resume = await createResume({
        source_document_id: resumeDocument.source_document_id,
        title: "本次面试准备简历",
        target_direction: "backend",
      }, signal);
      const job = await createJob({
        source_document_id: jobDocument.source_document_id,
        title: "本次目标岗位",
        target_direction: "backend",
      }, signal);
      const experience = experienceDocument
        ? await createExperience({
            source_document_id: experienceDocument.source_document_id,
            title: "本次补充面经",
            experience_type: "manual",
          }, signal)
        : null;

      setSubmissionStage("parsing");
      await parseResume(resume.resume_id, signal);
      await parseJob(job.job_description_id, signal);
      if (experience) await parseExperience(experience.interview_experience_id, signal);

      setSubmissionStage("package");
      return createPrepPackage({
        resume_id: resume.resume_id,
        job_description_id: job.job_description_id,
        interview_experience_ids: experience ? [experience.interview_experience_id] : [],
        preparation_goal: "围绕目标岗位完成结构化面试练习",
        title: "本次面试准备任务",
      }, signal);
    },
    onSuccess: (result) => {
      const suffix = isMockMode ? "&scenario=agent-running" : "";
      navigate(
        `/prep/${result.prep_package_id}/processing?agentRunId=${result.agent_run_id}${suffix}`,
      );
    },
    onError: (error) => {
      if (isAbortError(error)) setCancelled(true);
    },
    onSettled: () => {
      setSubmissionLocked(false);
      controllerRef.current = null;
    },
  });

  const advance = async () => {
    if (currentStep === "resume") {
      const textValid = await trigger("resume");
      if (!textValid) return;
      if (!file && getValues("resume").trim().length < 10) {
        setError("resume", { message: "请上传文件，或至少输入 10 个字符的简历内容。" });
        return;
      }
      clearErrors("resume");
    }
    if (currentStep === "job" && !(await trigger("job"))) return;
    const currentIndex = steps.findIndex((step) => step.id === currentStep);
    const next = steps[currentIndex + 1];
    if (!next) return;
    setCompleted((values) => [...new Set([...values, currentStep])]);
    setCurrentStep(next.id);
  };

  const startSubmit = (values: FormValues) => {
    if (submissionLocked || mutation.isPending) return;
    setSubmissionLocked(true);
    mutation.mutate(values);
  };
  const submit = handleSubmit(startSubmit);
  const apiError = mutation.error instanceof ApiError ? mutation.error : null;

  useEffect(() => {
    if (Object.keys(errors).length > 0 || fileError) errorSummaryRef.current?.focus();
  }, [errors, fileError]);

  if (mutation.isPending) {
    return (
      <div className="page-stack narrow-page">
        <header>
          <p className="eyebrow">创建面试准备任务</p>
          <h1>正在处理本次资料</h1>
          <p>当前接口会同步等待 Agent 完成；以下仅表示客户端请求阶段，不代表后台实时进度。</p>
        </header>
        <ProcessingStatus status="running" steps={submissionSteps(submissionStage)} />
        <button type="button" className="secondary-button" onClick={() => controllerRef.current?.abort()}>
          取消本次请求
        </button>
      </div>
    );
  }

  return (
    <div className="page-stack narrow-page">
      <header>
        <p className="eyebrow">创建面试准备任务</p>
        <h1>提供本次练习所需资料</h1>
        <p>内容只保存在当前页面内存中，不写入 localStorage。</p>
      </header>
      <Stepper steps={steps} currentStepId={currentStep} completedIds={completed} onStepSelect={setCurrentStep} />
      <form onSubmit={submit} noValidate>
        {Object.keys(errors).length > 0 || fileError ? (
          <div ref={errorSummaryRef} className="error-summary" role="alert" tabIndex={-1}>
            请检查当前步骤中标记的字段。
          </div>
        ) : null}
        {currentStep === "resume" ? (
          <div className="form-section">
            <UploadDropzone
              file={file}
              error={fileError}
              onSelect={(selected) => {
                if (!selected) return;
                const suffix = selected.name.slice(selected.name.lastIndexOf(".")).toLowerCase();
                if (!allowedUploadExtensions.includes(suffix)) {
                  setFile(null);
                  setFileError("仅支持 PDF、DOCX 或 TXT 文件。");
                  return;
                }
                if (selected.size > maxUploadBytes) {
                  setFile(null);
                  setFileError("文件不能超过 10 MiB。");
                  return;
                }
                setFileError(undefined);
                clearErrors("resume");
                setFile(selected);
              }}
              onCancel={() => {
                setFile(null);
                setFileError(undefined);
              }}
            />
            <Controller
              control={control}
              name="resume"
              render={({ field }) => <ResumeInput id="resume" {...field} error={errors.resume?.message} />}
            />
          </div>
        ) : null}
        {currentStep === "job" ? (
          <Controller
            control={control}
            name="job"
            render={({ field }) => <JobInput id="job" {...field} error={errors.job?.message} />}
          />
        ) : null}
        {currentStep === "experience" ? (
          <Controller
            control={control}
            name="experience"
            render={({ field }) => <ExperienceInput id="experience" {...field} error={errors.experience?.message} />}
          />
        ) : null}
        {currentStep === "review" ? (
          <section className="review-panel" aria-labelledby="review-title">
            <h2 id="review-title">确认提交</h2>
            <p>提交后将依次保存资料、同步解析并生成准备包。不会自动重复执行 POST。</p>
          </section>
        ) : null}
        {mutation.isError ? (
          <RetryPanel
            title={cancelled ? "本次请求已取消" : "准备任务未创建"}
            reason={cancelled ? "输入仍保留在当前页面，可修改后再次提交。" : (apiError?.message ?? "请求未完成，请稍后重试。")}
            retryable={!cancelled && (apiError?.retryable ?? false)}
            requestId={apiError?.requestId}
            onRetry={() => void submit()}
            onEdit={() => setCurrentStep("resume")}
          />
        ) : null}
        <div className="button-row form-actions">
          {currentStep !== "resume" ? (
            <button type="button" className="secondary-button" onClick={() => {
              const index = steps.findIndex((step) => step.id === currentStep);
              const previous = steps[index - 1];
              if (previous) setCurrentStep(previous.id);
            }}>返回上一步</button>
          ) : null}
          {currentStep === "review" ? (
            <button key="submit-prep-package" type="submit" disabled={mutation.isPending || submissionLocked}>生成准备包</button>
          ) : (
            <button
              key="advance-prep-step"
              type="button"
              onClick={(event) => {
                event.preventDefault();
                void advance();
              }}
            >下一步</button>
          )}
        </div>
      </form>
    </div>
  );
}
