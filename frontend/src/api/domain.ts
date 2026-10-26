import { z } from "zod";

export const sourceQualitySchema = z.enum([
  "trusted",
  "synthetic",
  "degraded",
  "user_provided",
  "mixed",
  "unknown",
]);
export const evaluationModeSchema = z.enum(["standard", "degraded"]);

export const scoreItemSchema = z.object({
  name: z.string(),
  score: z.number(),
  max_score: z.number().positive(),
  reason: z.string(),
});

export const evaluationSchema = z
  .object({
    evaluation_mode: evaluationModeSchema,
    score_available: z.boolean(),
    source_quality: sourceQualitySchema,
    degradation_reasons: z.array(z.string()),
    total_score: z.number().nullable(),
    dimension_scores: z.array(scoreItemSchema),
    overall_comment: z.string(),
    strengths: z.array(z.string()),
    improvement_points: z.array(z.string()),
    risks: z.array(z.string()),
    improved_answer: z.string(),
    follow_up_questions: z.array(z.string()),
    next_practice_suggestion: z.string(),
    memory_update: z.record(z.string(), z.unknown()),
  })
  .superRefine((value, context) => {
    if (value.evaluation_mode === "degraded") {
      if (value.score_available || value.total_score !== null || value.dimension_scores.length > 0) {
        context.addIssue({
          code: "custom",
          message: "degraded evaluation cannot expose precise scores",
        });
      }
    } else if (!value.score_available || value.total_score === null || value.dimension_scores.length === 0) {
      context.addIssue({
        code: "custom",
        message: "standard evaluation requires total and dimension scores",
      });
    }
  });

export const evaluationDetailSchema = z
  .object({
    answer_evaluation_id: z.string(),
    agent_run_id: z.string().nullable(),
    evaluation_mode: evaluationModeSchema,
    score_available: z.boolean(),
    source_quality: sourceQualitySchema,
    degradation_reasons: z.array(z.string()),
    total_score: z.number().nullable(),
    strengths: z.array(z.string()),
    improvement_points: z.array(z.string()),
    risks: z.array(z.string()),
    improved_answer: z.string(),
    follow_up_questions: z.array(z.string()),
    next_practice_suggestion: z.string(),
    memory_update: z.record(z.string(), z.unknown()),
    evaluation: evaluationSchema,
  });

export const questionSchema = z
  .object({
    question_db_id: z.string(),
    question_id: z.string(),
    module: z.enum(["self_intro", "professional", "behavior_project"]),
    question_text: z.string(),
    purpose: z.string(),
    difficulty: z.enum(["basic", "medium", "hard"]),
    source_type: z.enum(["resume", "jd", "experience", "inferred", "mixed"]),
    sort_order: z.number().int().positive(),
  });

export const questionListSchema = z.object({
  total: z.number().int().nonnegative(),
  items: z.array(questionSchema),
});

export const agentRunStepSchema = z
  .object({
    agent_run_step_id: z.string(),
    step_order: z.number().int().positive(),
    agent_name: z.string(),
    action_type: z.string(),
    status: z.enum(["pending", "running", "succeeded", "failed"]),
    latency_ms: z.number().nonnegative().nullable(),
  });

export const agentRunSchema = z
  .object({
    agent_run_id: z.string(),
    run_type: z.string(),
    status: z.enum(["pending", "running", "succeeded", "failed"]),
    execution_mode: z.enum(["mock", "real", "fallback"]),
    provider: z.string(),
    model_name: z.string().nullable(),
    prompt_version: z.string().nullable(),
    real_call_count: z.number().int().nonnegative(),
    retry_count: z.number().int().nonnegative(),
    latency_ms: z.number().nonnegative().nullable(),
    token_usage: z.object({
      input_tokens: z.number().int().nonnegative().nullable(),
      output_tokens: z.number().int().nonnegative().nullable(),
      total_tokens: z.number().int().nonnegative().nullable(),
    }),
    fallback_reason: z.record(z.string(), z.unknown()).nullable(),
    failure_types: z.record(z.string(), z.number()),
    steps: z.array(agentRunStepSchema),
  });

export const evaluationHistorySchema = z.object({
  total: z.number().int().nonnegative(),
  items: z.array(
    z.object({
        answer_evaluation_id: z.string(),
        prep_package_id: z.string().nullable(),
        agent_run_id: z.string().nullable(),
        evaluation_mode: evaluationModeSchema,
        score_available: z.boolean(),
        source_quality: sourceQualitySchema,
        degradation_reasons: z.array(z.string()),
        total_score: z.number().nullable(),
        created_at: z.string(),
      }),
  ),
});

export const documentCreatedSchema = z.object({
  source_document_id: z.string(),
  document_type: z.enum(["resume", "jd", "interview_experience"]),
  input_type: z.enum(["text", "upload"]),
  original_filename: z.string().nullable(),
  text_hash: z.string(),
  metadata: z.record(z.string(), z.unknown()),
  created_at: z.string(),
});

export const resumeCreatedSchema = z.object({
  resume_id: z.string(),
  source_document_id: z.string(),
  title: z.string(),
  target_direction: z.string().nullable(),
  version_label: z.string().nullable(),
  is_active: z.boolean(),
  created_at: z.string(),
});

export const jobCreatedSchema = z.object({
  job_description_id: z.string(),
  source_document_id: z.string(),
  title: z.string(),
  company_name: z.string().nullable(),
  job_url: z.string().nullable(),
  target_direction: z.string(),
  created_at: z.string(),
});

export const experienceCreatedSchema = z.object({
  interview_experience_id: z.string(),
  source_document_id: z.string(),
  title: z.string(),
  experience_type: z.string(),
  company_name: z.string().nullable(),
  role_name: z.string().nullable(),
  created_at: z.string(),
});

export const resumeParsedSchema = z.object({
  resume_id: z.string(),
  resume_profile_id: z.string(),
  agent_run_id: z.string(),
});

export const jobParsedSchema = z.object({
  job_description_id: z.string(),
  jd_profile_id: z.string(),
  agent_run_id: z.string(),
});

export const experienceParsedSchema = z.object({
  interview_experience_id: z.string(),
  experience_profile_id: z.string(),
  agent_run_id: z.string(),
});

export const prepPackageCreatedSchema = z.object({
  prep_package_id: z.string(),
  agent_run_id: z.string(),
  status: z.string(),
});

export const prepPackageDetailSchema = z.object({
  prep_package_id: z.string(),
  title: z.string(),
  status: z.string(),
  overview: z.record(z.string(), z.unknown()),
  question_count: z.number().int().nonnegative(),
  recommended_count: z.number().int().nonnegative(),
  created_at: z.string(),
});

export const evaluationCreatedSchema = z
  .object({
    answer_evaluation_id: z.string(),
    agent_run_id: z.string(),
    evaluation_mode: evaluationModeSchema,
    score_available: z.boolean(),
    source_quality: sourceQualitySchema,
    degradation_reasons: z.array(z.string()),
    total_score: z.number().nullable(),
  })
  .superRefine((value, context) => {
    if (!value.score_available && value.total_score !== null) {
      context.addIssue({ code: "custom", message: "unavailable score must be null" });
    }
    if (value.evaluation_mode === "degraded" && value.score_available) {
      context.addIssue({ code: "custom", message: "degraded evaluation cannot expose score" });
    }
  });

export const successEnvelopeSchema = <T extends z.ZodType>(dataSchema: T) =>
  z.object({
    data: dataSchema,
    message: z.string(),
    request_id: z.string(),
  });

export const apiErrorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.string(), z.unknown()),
  }),
});

export type SourceQuality = z.infer<typeof sourceQualitySchema>;
export type EvaluationMode = z.infer<typeof evaluationModeSchema>;
export type ScoreItem = z.infer<typeof scoreItemSchema>;
export type EvaluationDetail = z.infer<typeof evaluationDetailSchema>;
export type Question = z.infer<typeof questionSchema>;
export type QuestionList = z.infer<typeof questionListSchema>;
export type AgentRun = z.infer<typeof agentRunSchema>;
export type EvaluationHistory = z.infer<typeof evaluationHistorySchema>;
export type DocumentCreated = z.infer<typeof documentCreatedSchema>;
export type ResumeCreated = z.infer<typeof resumeCreatedSchema>;
export type JobCreated = z.infer<typeof jobCreatedSchema>;
export type ExperienceCreated = z.infer<typeof experienceCreatedSchema>;
export type PrepPackageDetail = z.infer<typeof prepPackageDetailSchema>;
export type EvaluationCreated = z.infer<typeof evaluationCreatedSchema>;
