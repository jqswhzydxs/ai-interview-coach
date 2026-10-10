# 数据库表设计 v0.1

## 1. 设计目标

本数据库设计服务于 AI Interview Coach Agent 的第一版 MVP：

1. 支持完整面试备战包生成。
2. 支持单题模拟回答评分。
3. 支持简历、JD、面经、面试转写文本的材料管理。
4. 支持 Agent 运行日志、结构化输出、评测和用户长期记忆。
5. 支持后续扩展到多用户、多岗位、多简历版本和 RAG。

## 2. 推荐技术选型

第一版确认使用 PostgreSQL。

原因：

1. 支持 `jsonb`，适合保存 Agent 的结构化输出。
2. 后续可以直接接 `pgvector` 做简历、JD、面经的向量检索。
3. 比 SQLite 更适合展示工程化能力。
4. 与 FastAPI、SQLAlchemy、Alembic 配合成熟。

本设计采用“关系表 + JSONB”的混合方式：

1. 业务主线关系用外键串起来。
2. Agent 输出结果先用 `jsonb` 保存，避免早期过度拆表。
3. 高频查询字段单独拆成列，例如 `role_name`、`score`、`status`、`module`。

## 3. 设计假设

当前按以下假设设计：

1. 第一版不做正式登录注册，但数据库预留 `users` 表，并使用默认用户。
2. 简历、JD、面经、转写文本都允许保存历史版本。
3. 上传的 PDF / DOCX 原文件保存到本地文件夹，数据库保存 `file_path` 和提取文本。
4. Agent 每次运行都要记录 `agent_runs`，方便排查、评测和简历展示。
5. 用户长期记忆用独立表保存，避免只藏在对话上下文里。
6. 第一版允许将简历、JD、面经的提取文本保存到数据库。隐私和脱敏策略后续再加强。
7. 第一版支持导出 Markdown 报告，因此保留 `interview_prep_packages.rendered_markdown` 字段。
8. 真实面试转写复盘先延后，`interview_reviews` 作为第二阶段表设计保留。

## 4. 表分组总览

### 4.1 用户与材料层

1. `users`：用户。
2. `source_documents`：原始材料统一表。
3. `resumes`：简历业务记录。
4. `resume_profiles`：简历结构化解析结果。
5. `job_descriptions`：岗位 JD 业务记录。
6. `jd_profiles`：JD 结构化解析结果。
7. `interview_experiences`：用户手动粘贴的面经或历史面试记录。
8. `experience_profiles`：面经结构化解析结果。

### 4.2 面试备战包层

1. `interview_prep_packages`：完整面试备战包主表。
2. `prep_package_experiences`：备战包与面经的关联表。
3. `match_reports`：简历-JD 差距分析报告。
4. `interview_questions`：岗位专属面试题库。
5. `prep_manuals`：面试备战要点手册。
6. `recommended_questions`：推荐先练的 3 道题。

### 4.3 练习与复盘层

1. `answer_evaluations`：单题模拟回答评分记录。
2. `interview_reviews`：真实面试转写文本复盘报告。

### 4.4 记忆、日志与评测层

1. `memory_items`：用户长期记忆。
2. `agent_runs`：Agent 运行主表。
3. `agent_run_steps`：Agent 运行步骤表。
4. `quality_evaluations`：系统输出质量评测记录。

## 5. 核心关系

```text
users
  ├─ resumes
  │   └─ resume_profiles
  ├─ job_descriptions
  │   └─ jd_profiles
  ├─ interview_experiences
  │   └─ experience_profiles
  ├─ interview_prep_packages
  │   ├─ match_reports
  │   ├─ interview_questions
  │   ├─ prep_manuals
  │   ├─ recommended_questions
  │   └─ answer_evaluations
  ├─ interview_reviews
  ├─ memory_items
  └─ agent_runs
      └─ agent_run_steps
```

## 6. 表结构设计

### 6.1 users

用于支持未来多用户。MVP 可以创建一个默认用户。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 用户 ID |
| display_name | varchar(100) | 用户展示名 |
| email | varchar(255), nullable | 邮箱，第一版可为空 |
| role | varchar(50) | 用户角色，默认 `candidate` |
| created_at | timestamptz | 创建时间 |
| updated_at | timestamptz | 更新时间 |

建议索引：

1. `idx_users_email`，唯一索引，可延后到登录注册阶段。

### 6.2 source_documents

统一保存用户上传或粘贴的原始材料，避免 PDF、DOCX、Markdown、纯文本各自散落。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 原始材料 ID |
| user_id | uuid fk | 所属用户 |
| document_type | varchar(50) | `resume`、`jd`、`interview_experience`、`interview_transcript` |
| input_type | varchar(50) | `pdf`、`docx`、`markdown`、`text` |
| original_filename | varchar(255), nullable | 原文件名 |
| file_path | text, nullable | 文件存储路径 |
| raw_text | text | 提取或粘贴后的正文 |
| text_hash | varchar(64) | 正文 hash，用于去重 |
| metadata | jsonb | 页数、字数、解析工具版本等 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_source_documents_user_type`：`user_id, document_type`。
2. `idx_source_documents_text_hash`：`text_hash`。

### 6.3 resumes

简历业务记录。它引用原始文档，并承载简历版本概念。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 简历 ID |
| user_id | uuid fk | 所属用户 |
| source_document_id | uuid fk | 对应原始材料 |
| title | varchar(200) | 简历名称，例如“后端实习简历 v1” |
| target_direction | varchar(100), nullable | 目标方向，例如 `backend` |
| version_label | varchar(50), nullable | 用户自定义版本号 |
| is_active | boolean | 是否为当前默认简历 |
| created_at | timestamptz | 创建时间 |
| updated_at | timestamptz | 更新时间 |

建议索引：

1. `idx_resumes_user_active`：`user_id, is_active`。

### 6.4 resume_profiles

保存 Resume Analyzer Agent 的结构化输出。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 简历解析结果 ID |
| resume_id | uuid fk | 所属简历 |
| agent_run_id | uuid fk, nullable | 产生该结果的 Agent 运行 |
| schema_version | varchar(50) | 结构版本 |
| profile_json | jsonb | ResumeProfile 完整结构 |
| skills | jsonb | 技能列表，便于查询 |
| projects | jsonb | 项目列表 |
| backend_tags | jsonb | 后端能力标签 |
| risk_points | jsonb | 表达风险点 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_resume_profiles_resume_created`：`resume_id, created_at desc`。
2. `gin_resume_profiles_skills`：`skills` 的 GIN 索引，可后续添加。

### 6.5 job_descriptions

保存用户输入的目标岗位 JD。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | JD ID |
| user_id | uuid fk | 所属用户 |
| source_document_id | uuid fk, nullable | 对应原始材料 |
| title | varchar(200) | 岗位名称 |
| company_name | varchar(200), nullable | 公司名称 |
| job_url | text, nullable | 岗位链接，第一版可为空 |
| raw_text | text | JD 原文 |
| target_direction | varchar(100) | 第一版默认 `backend` |
| created_at | timestamptz | 创建时间 |
| updated_at | timestamptz | 更新时间 |

建议索引：

1. `idx_job_descriptions_user_created`：`user_id, created_at desc`。
2. `idx_job_descriptions_direction`：`target_direction`。

### 6.6 jd_profiles

保存 JD Analyzer Agent 的结构化输出。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | JD 解析结果 ID |
| job_description_id | uuid fk | 所属 JD |
| agent_run_id | uuid fk, nullable | 产生该结果的 Agent 运行 |
| schema_version | varchar(50) | 结构版本 |
| profile_json | jsonb | JDProfile 完整结构 |
| core_responsibilities | jsonb | 核心职责 |
| hard_requirements | jsonb | 硬性要求 |
| bonus_points | jsonb | 加分项 |
| tech_keywords | jsonb | 技术关键词 |
| backend_dimensions | jsonb | 后端能力维度 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_jd_profiles_jd_created`：`job_description_id, created_at desc`。
2. `gin_jd_profiles_keywords`：`tech_keywords` 的 GIN 索引，可后续添加。

### 6.7 interview_experiences

保存用户手动粘贴的面经、历史面试记录或笔试面试题。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 面经 ID |
| user_id | uuid fk | 所属用户 |
| source_document_id | uuid fk, nullable | 对应原始材料 |
| title | varchar(200) | 面经标题 |
| experience_type | varchar(50) | `online_shared`、`self_history`、`written_test`、`interview_transcript` |
| company_name | varchar(200), nullable | 公司名称 |
| role_name | varchar(200), nullable | 岗位名称 |
| raw_text | text | 面经正文 |
| occurred_at | date, nullable | 面试或记录发生日期 |
| created_at | timestamptz | 创建时间 |
| updated_at | timestamptz | 更新时间 |

建议索引：

1. `idx_interview_experiences_user_type`：`user_id, experience_type`。
2. `idx_interview_experiences_role`：`role_name`。

### 6.8 experience_profiles

保存 Interview Experience Analyzer Agent 的结构化输出。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 面经解析结果 ID |
| interview_experience_id | uuid fk | 所属面经 |
| agent_run_id | uuid fk, nullable | 产生该结果的 Agent 运行 |
| schema_version | varchar(50) | 结构版本 |
| profile_json | jsonb | ExperienceProfile 完整结构 |
| frequent_questions | jsonb | 高频问题 |
| frequent_topics | jsonb | 高频知识点 |
| follow_up_patterns | jsonb | 追问模式 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_experience_profiles_exp_created`：`interview_experience_id, created_at desc`。

## 7. 面试备战包表

### 7.1 interview_prep_packages

完整面试备战包主表。一次“简历 + JD + 可选面经”的生成结果对应一条记录。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 备战包 ID |
| user_id | uuid fk | 所属用户 |
| resume_id | uuid fk | 使用的简历 |
| resume_profile_id | uuid fk | 使用的简历解析结果 |
| job_description_id | uuid fk | 使用的 JD |
| jd_profile_id | uuid fk | 使用的 JD 解析结果 |
| agent_run_id | uuid fk, nullable | 产生该备战包的 Agent 运行 |
| title | varchar(200) | 备战包标题 |
| status | varchar(50) | `generating`、`ready`、`failed` |
| package_version | varchar(50) | 备战包版本 |
| overview_json | jsonb | 备战总览 |
| priority_plan_json | jsonb | 面试准备优先级 |
| action_items_json | jsonb | 下一步行动清单 |
| rendered_markdown | text, nullable | 最终报告 Markdown |
| created_at | timestamptz | 创建时间 |
| updated_at | timestamptz | 更新时间 |

建议索引：

1. `idx_prep_packages_user_created`：`user_id, created_at desc`。
2. `idx_prep_packages_resume_jd`：`resume_id, job_description_id`。
3. `idx_prep_packages_status`：`status`。

### 7.2 prep_package_experiences

备战包与面经的多对多关联表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 关联 ID |
| prep_package_id | uuid fk | 备战包 |
| interview_experience_id | uuid fk | 面经 |
| experience_profile_id | uuid fk, nullable | 使用的面经解析结果 |
| relevance_score | numeric(5,2), nullable | 与当前 JD 的相关性 |
| created_at | timestamptz | 创建时间 |

建议唯一约束：

1. `uniq_package_experience`：`prep_package_id, interview_experience_id`。

### 7.3 match_reports

保存简历-JD 差距分析报告。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 匹配报告 ID |
| prep_package_id | uuid fk | 所属备战包 |
| agent_run_id | uuid fk, nullable | 产生该报告的 Agent 运行 |
| overall_score | numeric(5,2) | 总体匹配度，0-100 |
| strengths_json | jsonb | 匹配优势 |
| gaps_json | jsonb | 缺失能力 |
| expression_issues_json | jsonb | 表达不足 |
| risk_points_json | jsonb | 风险点 |
| resume_suggestions_json | jsonb | 简历修改建议 |
| evidence_refs_json | jsonb | 证据引用 |
| report_json | jsonb | MatchReport 完整结构 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_match_reports_package`：`prep_package_id`。
2. `idx_match_reports_score`：`overall_score`。

### 7.4 interview_questions

保存岗位专属面试题库中的每一道题。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 数据库题目 ID |
| prep_package_id | uuid fk | 所属备战包 |
| question_id | varchar(80) | 题库内稳定编号，例如 `Q-PRO-001` |
| module | varchar(50) | `self_intro`、`professional`、`behavior_project` |
| question_text | text | 问题正文 |
| purpose | text | 考察目的 |
| difficulty | varchar(50) | `basic`、`medium`、`hard` |
| source_type | varchar(50) | `resume`、`jd`、`experience`、`inferred`、`mixed` |
| source_refs_json | jsonb | 来源依据 |
| jd_keywords_json | jsonb | JD 匹配关键词 |
| answer_framework | text | 高分回答框架 |
| star_template | text | STAR 模板 |
| scoring_anchors_json | jsonb | 评分锚点 |
| follow_up_questions_json | jsonb | 连环追问 |
| preparation_advice | text | 备考建议 |
| sort_order | integer | 展示顺序 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_questions_package_module`：`prep_package_id, module`。
2. `uniq_questions_package_question_id`：`prep_package_id, question_id`。
3. `idx_questions_difficulty`：`difficulty`。

### 7.5 prep_manuals

保存面试备战要点手册。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 手册 ID |
| prep_package_id | uuid fk | 所属备战包 |
| agent_run_id | uuid fk, nullable | 产生该手册的 Agent 运行 |
| bonus_points_json | jsonb | 回答加分点，至少 8 条 |
| red_flags_json | jsonb | 回答雷点，至少 6 条 |
| resume_alignment_json | jsonb | 简历细节匹配建议 |
| speaking_tactics_json | jsonb | 现场话术节奏建议 |
| reverse_questions_json | jsonb | 反问环节话术 |
| manual_json | jsonb | PrepManual 完整结构 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_prep_manuals_package`：`prep_package_id`。

### 7.6 recommended_questions

保存“推荐先练的 3 道题”。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 推荐 ID |
| prep_package_id | uuid fk | 所属备战包 |
| question_db_id | uuid fk | 对应 `interview_questions.id` |
| rank | integer | 推荐顺序，1 到 3 |
| reason | text | 推荐理由 |
| related_weaknesses_json | jsonb | 对应薄弱点 |
| created_at | timestamptz | 创建时间 |

建议唯一约束：

1. `uniq_recommended_package_rank`：`prep_package_id, rank`。
2. `uniq_recommended_package_question`：`prep_package_id, question_db_id`。

## 8. 练习与复盘表

### 8.1 answer_evaluations

保存单题模拟回答评分结果。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 评分记录 ID |
| user_id | uuid fk | 所属用户 |
| prep_package_id | uuid fk, nullable | 所属备战包 |
| question_db_id | uuid fk, nullable | 对应题库题目 |
| custom_question_text | text, nullable | 用户手动输入题目 |
| user_answer | text | 用户原始回答 |
| agent_run_id | uuid fk, nullable | 产生评分的 Agent 运行 |
| total_score | numeric(5,2) | 总分，0-100 |
| relevance_score | numeric(5,2) | 相关性，0-20 |
| technical_accuracy_score | numeric(5,2) | 技术准确性，0-25 |
| project_specificity_score | numeric(5,2) | 项目具体性，0-20 |
| structure_score | numeric(5,2) | 结构性，0-15 |
| communication_score | numeric(5,2) | 表达力，0-10 |
| risk_control_score | numeric(5,2) | 风险控制，0-10 |
| strengths_json | jsonb | 表现好的地方 |
| improvement_points_json | jsonb | 需要改进的地方 |
| risks_json | jsonb | 技术错误或表达风险 |
| improved_answer | text | 改进版回答 |
| follow_up_questions_json | jsonb | 可能追问 |
| next_practice_suggestion | text | 下一题建议 |
| memory_update_json | jsonb | 记忆更新建议 |
| evaluation_json | jsonb | AnswerEvaluation 完整结构 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_answer_evaluations_user_created`：`user_id, created_at desc`。
2. `idx_answer_evaluations_question`：`question_db_id`。
3. `idx_answer_evaluations_total_score`：`total_score`。

### 8.2 interview_reviews

保存真实面试转写文本或面试回忆的复盘结果。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 面试复盘 ID |
| user_id | uuid fk | 所属用户 |
| prep_package_id | uuid fk, nullable | 关联备战包 |
| source_document_id | uuid fk, nullable | 转写文本来源 |
| agent_run_id | uuid fk, nullable | 产生复盘的 Agent 运行 |
| title | varchar(200) | 复盘标题 |
| transcript_text | text | 转写文本或面试回忆 |
| extracted_questions_json | jsonb | 面试问题列表 |
| answer_summaries_json | jsonb | 用户回答摘要 |
| strengths_json | jsonb | 表现好的地方 |
| weaknesses_json | jsonb | 需要改进的地方 |
| technical_gaps_json | jsonb | 技术知识短板 |
| communication_issues_json | jsonb | 表达与沟通问题 |
| next_plan_json | jsonb | 下一轮准备计划 |
| review_json | jsonb | InterviewReviewReport 完整结构 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_interview_reviews_user_created`：`user_id, created_at desc`。
2. `idx_interview_reviews_package`：`prep_package_id`。

## 9. 记忆、日志与评测表

### 9.1 memory_items

保存用户长期记忆。它是自进化闭环的核心。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 记忆 ID |
| user_id | uuid fk | 所属用户 |
| memory_type | varchar(50) | `weakness`、`strength`、`preference`、`target_role`、`project_pattern` |
| category | varchar(100) | 例如 `database`、`communication`、`project_experience` |
| content | text | 记忆内容 |
| evidence_json | jsonb | 支撑证据 |
| confidence | numeric(4,3) | 置信度，0-1 |
| source_type | varchar(50) | `answer_evaluation`、`interview_review`、`user_feedback`、`manual` |
| source_id | uuid, nullable | 来源记录 ID |
| status | varchar(50) | `active`、`archived`、`rejected` |
| created_at | timestamptz | 创建时间 |
| updated_at | timestamptz | 更新时间 |

建议索引：

1. `idx_memory_items_user_type`：`user_id, memory_type`。
2. `idx_memory_items_user_status`：`user_id, status`。

### 9.2 agent_runs

保存一次 Agent 工作流运行。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 运行 ID |
| user_id | uuid fk | 所属用户 |
| run_type | varchar(80) | `parse_resume`、`parse_jd`、`generate_prep_package`、`evaluate_answer`、`review_interview` |
| status | varchar(50) | `queued`、`running`、`succeeded`、`failed` |
| model_name | varchar(100), nullable | 使用模型 |
| prompt_version | varchar(100), nullable | Prompt 版本 |
| input_summary_json | jsonb | 输入摘要，不必保存完整敏感文本 |
| output_summary_json | jsonb | 输出摘要 |
| error_message | text, nullable | 错误信息 |
| started_at | timestamptz | 开始时间 |
| finished_at | timestamptz, nullable | 结束时间 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_agent_runs_user_created`：`user_id, created_at desc`。
2. `idx_agent_runs_type_status`：`run_type, status`。

### 9.3 agent_run_steps

保存一次 Agent 运行中的步骤。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 步骤 ID |
| agent_run_id | uuid fk | 所属运行 |
| step_order | integer | 步骤顺序 |
| agent_name | varchar(100) | Agent 名称 |
| action_type | varchar(80) | `llm_call`、`tool_call`、`validation`、`memory_update` |
| input_json | jsonb | 步骤输入摘要 |
| output_json | jsonb | 步骤输出摘要 |
| status | varchar(50) | `succeeded`、`failed`、`skipped` |
| error_message | text, nullable | 错误信息 |
| latency_ms | integer, nullable | 耗时 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_agent_run_steps_run_order`：`agent_run_id, step_order`。
2. `idx_agent_run_steps_agent`：`agent_name`。

### 9.4 quality_evaluations

保存系统输出质量评测结果，用于评测机制和 Prompt 迭代。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid pk | 评测 ID |
| user_id | uuid fk, nullable | 所属用户，可为空 |
| target_type | varchar(80) | `prep_package`、`question_bank`、`answer_evaluation`、`match_report` |
| target_id | uuid | 被评测对象 ID |
| evaluator_type | varchar(50) | `human`、`llm_judge`、`rule_based` |
| rubric_version | varchar(100) | 评测 Rubric 版本 |
| score | numeric(5,2) | 总分 |
| dimension_scores_json | jsonb | 分项分数 |
| comments | text, nullable | 评测说明 |
| created_at | timestamptz | 创建时间 |

建议索引：

1. `idx_quality_evaluations_target`：`target_type, target_id`。
2. `idx_quality_evaluations_score`：`score`。

## 10. MVP 必建表与可延后表

### 10.1 MVP 必建表

第一版建议先建这些表：

1. `users`
2. `source_documents`
3. `resumes`
4. `resume_profiles`
5. `job_descriptions`
6. `jd_profiles`
7. `interview_experiences`
8. `experience_profiles`
9. `interview_prep_packages`
10. `prep_package_experiences`
11. `match_reports`
12. `interview_questions`
13. `prep_manuals`
14. `recommended_questions`
15. `answer_evaluations`
16. `memory_items`
17. `agent_runs`
18. `agent_run_steps`

### 10.2 可以延后

这些表可以第二阶段再做：

1. `interview_reviews`：如果真实面试转写复盘先不做深。
2. `quality_evaluations`：如果第一版先手工评测，不做系统化评测面板。

## 11. 数据库设计原则

### 11.1 为什么不全部拆成细表

Agent 输出结构会频繁变化。例如题库、评分、手册字段后面很可能调整。如果第一版把每个加分点、每个雷点、每个评分理由都拆成单独表，会导致迁移成本很高。

所以第一版采取：

1. 核心对象单独建表。
2. 高频检索字段单独成列。
3. 复杂结构放 `jsonb`。

### 11.2 为什么保留 agent_runs

Agent 项目放简历时，`agent_runs` 和 `agent_run_steps` 很有价值，因为它能体现：

1. 有 Harness 编排。
2. 有多 Agent 执行链路。
3. 有可观测性。
4. 有失败重试和调试依据。
5. 有评测和 Prompt 版本管理基础。

### 11.3 为什么需要 memory_items

如果没有长期记忆，系统每次都是一次性报告生成，缺少“自进化”味道。

`memory_items` 可以支持：

1. 记录用户反复答不好的知识点。
2. 记录用户擅长的项目表达。
3. 让下一次题库生成更有针对性。
4. 让单题评分后能进入下一轮训练。

## 12. 需要你确认的问题

当前已确认：

1. 第一版直接使用 PostgreSQL。
2. 第一版暂时不做登录注册，但保留 `users` 表并使用默认用户。
3. 上传的 PDF / DOCX 原文件保存到本地文件夹，数据库保存 `file_path` 和提取文本。
4. 第一版允许将简历、JD、面经的提取文本保存进数据库。
5. 真实面试转写复盘暂不进入第一版主线，`interview_reviews` 可以先不建。
6. 第一版支持导出 Markdown 报告，保留 `interview_prep_packages.rendered_markdown` 字段。
7. 第一版不做质量评测后台，`quality_evaluations` 可以先用文档定义，后续再建。

后续仍可再确认：

1. 本地上传文件的具体目录，例如 `storage/uploads`。
2. 默认用户的初始化方式，例如启动时自动创建或迁移脚本创建。
3. 文本保存是否需要简单脱敏，例如隐藏手机号、邮箱。
4. 是否要在第二阶段引入 `pgvector`。
