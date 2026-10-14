# MVP 第一阶段实现计划：面试问题生成与单题评价 v0.1

## 1. 计划目标

本实现计划对应：

`docs/17-mvp-question-generation-and-answer-evaluation-spec-v0.1.md`

目标是实现一条可验证的 MVP 闭环：

```text
用户输入简历 + 目标岗位 JD + 准备目标
↓
系统解析简历和 JD
↓
系统生成岗位相关面试问题
↓
用户选择或输入一道题并提交答案
↓
系统输出结构化单题评价
```

本计划只覆盖已确认范围，不加入自动联网搜索、正式前端、登录注册、真实语音、PDF 导出、真实面试复盘或质量评测后台。

## 2. 技术基线

已确定技术栈：

1. Python 3.11。
2. `uv + pyproject.toml`。
3. FastAPI。
4. SQLAlchemy 2.x。
5. Alembic。
6. PostgreSQL。
7. Pydantic v2。
8. PyMuPDF、python-docx、Markdown / 纯文本解析。
9. 轻量 Harness。
10. mock/stub Agent 先行。
11. LLMClient 抽象，优先适配 DeepSeek，预留 Kimi。

项目分层：

```text
app/api/v1/routes
app/core
app/db/models
app/schemas
app/services
app/agents
app/agents/prompts
app/tools
tests/unit
tests/integration
tests/e2e
```

## 3. 实现边界

### 3.1 本计划实现

1. 材料保存：简历、JD、可选面经。
2. 简历解析：生成 `ResumeProfile`。
3. JD 解析：生成 `JDProfile`。
4. 可选面经解析：生成 `ExperienceProfile`。
5. 匹配分析：生成 `MatchReport`。
6. 题库生成：生成 `QuestionBank`。
7. 推荐先练 3 道题。
8. 单题答案评分：生成 `AnswerEvaluation`。
9. 记忆更新建议：生成或保存 `memory_update`。
10. Agent 运行日志：写入 `agent_runs` 和 `agent_run_steps`。
11. 使用 mock Agent 跑通完整流程。
12. 单元测试、集成测试、端到端测试。

### 3.2 本计划不实现

1. `interview_reviews`。
2. `quality_evaluations`。
3. 自动联网搜索。
4. 招聘网站爬虫。
5. 登录注册。
6. 正式前端。
7. 实时语音。
8. PDF 导出。
9. 异步任务队列。

## 4. 数据设计计划

### 4.1 需要使用的表

本 feature 需要使用或写入：

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
13. `recommended_questions`
14. `answer_evaluations`
15. `memory_items`
16. `agent_runs`
17. `agent_run_steps`

不建表：

1. `interview_reviews`
2. `quality_evaluations`

### 4.2 准备目标的落库方式

当前数据库 schema 未单独定义 `preparation_goal` 字段。

实现策略：

1. API 请求允许传入 `preparation_goal`。
2. `preparation_goal` 写入 `agent_runs.input_summary_json`。
3. `preparation_goal` 写入 `interview_prep_packages.overview_json`。
4. 不为 `preparation_goal` 单独新增数据库列。

原因：

1. 准备目标是生成上下文，不是当前高频查询字段。
2. 避免为了单一文本输入扩表。
3. 后续如果出现筛选和统计需求，再迁移成独立列。

### 4.3 MVP 首轮迁移

迁移应包含：

1. 用户与材料层表。
2. 简历 / JD / 面经 profile 表。
3. 备战包、匹配报告、题库、推荐题。
4. 单题评分。
5. 记忆。
6. Agent run 和 step。

迁移不包含：

1. 真实面试复盘表。
2. 质量评测表。

## 5. Schema 实现计划

### 5.1 通用 Schema

文件：

1. `app/schemas/common.py`
2. `app/schemas/response.py`
3. `app/schemas/pagination.py`

对象：

1. `EvidenceRef`
2. `ScoreItem`
3. `ActionItem`
4. 统一成功响应。
5. 统一错误响应。
6. `limit + offset` 分页参数。

校验：

1. `ScoreItem.score <= max_score`。
2. `EvidenceRef.source_type` 限定为 `resume`、`jd`、`experience`、`answer`、`inferred`、`mixed`。
3. 分页 limit 默认值和最大值受控。

### 5.2 Profile Schema

文件：

1. `app/schemas/resume.py`
2. `app/schemas/job_description.py`
3. `app/schemas/experience.py`

对象：

1. `ResumeProfile`
2. `JDProfile`
3. `ExperienceProfile`

要求：

1. 包含 `schema_version`、`generated_at`、`agent_name`、`prompt_version`。
2. 简历项目经历包含 evidence refs。
3. JD profile 包含核心职责、硬性要求、加分项、技术关键词、后端能力维度。

### 5.3 问题生成 Schema

文件：

1. `app/schemas/question.py`
2. `app/schemas/prep_package.py`

对象：

1. `MatchReport`
2. `InterviewQuestion`
3. `QuestionBank`
4. `RecommendedQuestion`
5. `InterviewPrepPackage`

硬性校验：

1. `QuestionBank.total_count >= 25`。
2. 三个模块每个不少于 8 道。
3. 同一题库内 `question_id` 唯一。
4. 每题必须有 `source_refs`。
5. 每题必须有 `scoring_anchors`。

### 5.4 单题评价 Schema

文件：

1. `app/schemas/evaluation.py`
2. `app/schemas/memory.py`

对象：

1. `AnswerEvaluation`
2. `MemoryItem`

硬性校验：

1. 总分 0 到 100。
2. 相关性 0 到 20。
3. 技术准确性 0 到 25。
4. 项目具体性 0 到 20。
5. 结构性 0 到 15。
6. 表达力 0 到 10。
7. 风险控制 0 到 10。
8. 至少包含 1 个改进建议。
9. 至少包含 1 个可能追问。

## 6. API 实现计划

### 6.1 通用 API 能力

文件：

1. `app/main.py`
2. `app/api/v1/router.py`
3. `app/core/middleware.py`
4. `app/core/errors.py`

实现：

1. `/api/v1` 基础路由。
2. `request_id` 中间件。
3. 统一成功响应。
4. 统一错误响应。
5. 错误码：`VALIDATION_ERROR`、`NOT_FOUND`、`AGENT_FAILED`、`INTERNAL_ERROR`。

### 6.2 材料接口

文件：

1. `app/api/v1/routes/documents.py`
2. `app/services/document_service.py`
3. `app/tools/file_parser.py`
4. `app/tools/text_utils.py`

接口：

1. `POST /api/v1/documents/upload`
2. `POST /api/v1/documents/text`

实现：

1. 支持简历 PDF / DOCX / Markdown / text。
2. 支持 JD 文本或 Markdown。
3. 支持可选面经文本。
4. 文件大小限制 5MB。
5. 文本 hash 使用 SHA-256。
6. Agent 输入和日志摘要中脱敏手机号、邮箱。
7. 写入 `source_documents`。

### 6.3 简历与 JD 接口

文件：

1. `app/api/v1/routes/resumes.py`
2. `app/api/v1/routes/jobs.py`
3. `app/services/resume_service.py`
4. `app/services/job_service.py`

接口：

1. `POST /api/v1/resumes`
2. `POST /api/v1/resumes/{resume_id}/parse`
3. `POST /api/v1/jobs`
4. `POST /api/v1/jobs/{job_description_id}/parse`

实现：

1. 创建简历业务记录。
2. 创建 JD 业务记录。
3. 使用 Harness 调用 Resume Analyzer Agent。
4. 使用 Harness 调用 JD Analyzer Agent。
5. 保存 `resume_profiles` 和 `jd_profiles`。
6. 响应返回 profile ID、agent_run_id 和结构化 profile。

### 6.4 可选面经接口

文件：

1. `app/api/v1/routes/experiences.py`
2. `app/services/experience_service.py`

接口：

1. `POST /api/v1/experiences`
2. `POST /api/v1/experiences/{interview_experience_id}/parse`

实现：

1. 保存用户手动粘贴面经。
2. 可选解析成 `ExperienceProfile`。
3. 没有面经时，问题生成流程仍可执行。

### 6.5 面试问题生成接口

文件：

1. `app/api/v1/routes/prep_packages.py`
2. `app/services/prep_package_service.py`
3. `app/services/question_service.py`

接口：

1. `POST /api/v1/prep-packages`
2. `GET /api/v1/prep-packages/{prep_package_id}`
3. `GET /api/v1/prep-packages/{prep_package_id}/questions`

请求：

```json
{
  "resume_id": "uuid",
  "job_description_id": "uuid",
  "interview_experience_ids": ["uuid"],
  "preparation_goal": "准备后端开发实习一面",
  "title": "后端开发实习备战"
}
```

实现：

1. 同步生成备战包。
2. 保留 `status` 和 `agent_run_id`。
3. 同步超时建议 120 秒。
4. 生成 `MatchReport`。
5. 生成 `QuestionBank`。
6. 写入 `interview_questions`。
7. 写入 `recommended_questions`。
8. 查询题库支持 `module` 和 `difficulty` 过滤。

### 6.6 单题评价接口

文件：

1. `app/api/v1/routes/evaluations.py`
2. `app/services/evaluation_service.py`
3. `app/services/memory_service.py`

接口：

1. `POST /api/v1/evaluations`
2. `GET /api/v1/evaluations/{answer_evaluation_id}`
3. `GET /api/v1/evaluations`

请求支持题库题目：

```json
{
  "prep_package_id": "uuid",
  "question_db_id": "uuid",
  "user_answer": "..."
}
```

请求支持自定义题目：

```json
{
  "custom_question_text": "请介绍你项目中的数据库设计",
  "user_answer": "..."
}
```

实现：

1. 题库题目评分时加载题目、评分锚点、ResumeProfile、JDProfile。
2. 自定义题目评分时使用用户提交题目和答案。
3. 调用 Answer Evaluator Agent。
4. 保存 `answer_evaluations`。
5. 生成 `memory_update`。
6. 高置信度记忆写入 `memory_items`。
7. 低置信度记忆仅保存在评分记录中。

### 6.7 Agent 运行日志接口

文件：

1. `app/api/v1/routes/agent_runs.py`
2. `app/services/agent_run_service.py`

接口：

1. `GET /api/v1/agent-runs/{agent_run_id}`

实现：

1. 返回 run_type、status、prompt_version、steps、error_message。
2. steps 按 `step_order` 排序。
3. 默认不返回完整敏感原文。

## 7. Agent 与 Routing 实现计划

### 7.1 Agent 基础设施

文件：

1. `app/agents/base.py`
2. `app/agents/harness.py`
3. `app/agents/llm_client.py`
4. `app/agents/mock_client.py`
5. `app/agents/prompt_loader.py`

实现：

1. `LLMClient` 抽象。
2. `MockLLMClient`。
3. DeepSeek Provider 骨架。
4. Kimi Provider 骨架。
5. Prompt 文件加载。
6. Harness run 和 step 记录。
7. Pydantic Schema 校验。
8. 校验失败重试一次。

### 7.2 问题生成 Agent 路由

路由：

```text
parse_resume
↓
parse_jd
↓
parse_experiences
↓
match_resume_to_jd
↓
generate_question_bank
↓
select_recommended_questions
```

Agent 文件：

1. `app/agents/resume_analyzer.py`
2. `app/agents/jd_analyzer.py`
3. `app/agents/experience_analyzer.py`
4. `app/agents/matching_agent.py`
5. `app/agents/question_bank_agent.py`

Prompt 文件：

1. `app/agents/prompts/resume_analyzer_v0.1.md`
2. `app/agents/prompts/jd_analyzer_v0.1.md`
3. `app/agents/prompts/experience_analyzer_v0.1.md`
4. `app/agents/prompts/matching_agent_v0.1.md`
5. `app/agents/prompts/question_bank_agent_v0.1.md`

输出：

1. `ResumeProfile`
2. `JDProfile`
3. `ExperienceProfile`
4. `MatchReport`
5. `QuestionBank`

### 7.3 单题评价 Agent 路由

路由：

```text
load_question
↓
load_resume_profile_and_jd_profile
↓
evaluate_answer
↓
update_memory
↓
save_answer_evaluation
```

Agent 文件：

1. `app/agents/answer_evaluator.py`
2. `app/agents/memory_agent.py`

Prompt 文件：

1. `app/agents/prompts/answer_evaluator_v0.1.md`
2. `app/agents/prompts/memory_agent_v0.1.md`

输出：

1. `AnswerEvaluation`
2. `MemoryItem` 或 memory update 建议。

## 8. 里程碑计划

### M1 项目基础

目标：

建立可启动、可测试的 FastAPI 后端。

任务：

1. 创建项目目录。
2. 配置 `pyproject.toml`。
3. 配置 `.env.example`。
4. 实现配置读取。
5. 实现日志。
6. 实现 request_id。
7. 实现 `/api/v1/health`。

验收：

1. 服务可启动。
2. `/api/v1/health` 返回 `ok`。
3. 测试可运行。

### M2 数据库与迁移

目标：

建立 MVP 必需数据结构。

任务：

1. 配置 SQLAlchemy。
2. 配置 Alembic。
3. 实现 MVP 必建 ORM 模型。
4. 生成初始迁移。
5. 应用启动时创建默认用户。

验收：

1. `alembic upgrade head` 成功。
2. 数据库存在默认用户。
3. 不包含 `interview_reviews` 和 `quality_evaluations`。

### M3 Schema 与工具

目标：

实现结构化契约和输入处理工具。

任务：

1. 实现通用 Schema。
2. 实现 Profile Schema。
3. 实现 QuestionBank Schema。
4. 实现 AnswerEvaluation Schema。
5. 实现 SHA-256 hash。
6. 实现手机号、邮箱脱敏。
7. 实现文件解析工具。

验收：

1. Schema 单元测试通过。
2. 题库数量约束可自动校验。
3. 单题评分分数范围可自动校验。
4. 文本 hash 稳定。

### M4 材料、简历、JD 入库与解析

目标：

支持用户输入材料并生成基础 profile。

任务：

1. 实现材料文本接口。
2. 实现材料上传接口。
3. 实现简历创建接口。
4. 实现 JD 创建接口。
5. 实现 Resume Analyzer mock。
6. 实现 JD Analyzer mock。

验收：

1. 文本简历和 JD 能保存。
2. 简历能生成 `ResumeProfile`。
3. JD 能生成 `JDProfile`。
4. Agent run 和 step 被记录。

### M5 问题生成闭环

目标：

基于简历、JD、准备目标生成面试题库。

任务：

1. 实现 Matching Agent mock。
2. 实现 Question Bank Agent mock。
3. 实现备战包生成服务。
4. 保存 `match_reports`。
5. 保存 `interview_questions`。
6. 保存 `recommended_questions`。
7. 实现题库查询 API。

验收：

1. 生成题库不少于 25 道。
2. 三个模块每个不少于 8 道。
3. 每道题有标准字段。
4. 推荐先练题数量为 3。
5. 项目追问不编造简历外经历。

### M6 单题评价闭环

目标：

支持用户提交答案并获得结构化评价。

任务：

1. 实现 Answer Evaluator Agent mock。
2. 实现 Memory Agent mock。
3. 实现单题评价服务。
4. 实现评分提交 API。
5. 实现评分详情 API。
6. 实现历史评分 API。
7. 实现记忆写入策略。

验收：

1. 支持题库题目评分。
2. 支持自定义题目评分。
3. 输出总分和分项分。
4. 输出扣分原因。
5. 输出改进版回答。
6. 输出可能追问。
7. 输出下一题建议。
8. 保存 `answer_evaluations`。

### M7 日志与验收测试

目标：

验证 MVP feature 可以端到端运行。

任务：

1. 实现 Agent run 查询 API。
2. 准备 2 到 3 组固定样例。
3. 编写 Schema 单元测试。
4. 编写 API 集成测试。
5. 编写端到端测试。

验收：

1. `uv run pytest tests/unit` 通过。
2. `uv run pytest tests/integration` 通过。
3. `uv run pytest tests/e2e` 通过。
4. mock Agent 可完整跑通“输入简历 + JD -> 生成题库 -> 提交答案 -> 获得评价”。

## 9. 测试计划

### 9.1 单元测试

覆盖：

1. Pydantic Schema。
2. QuestionBank 数量约束。
3. AnswerEvaluation 分数约束。
4. 文本 hash。
5. 脱敏工具。
6. Prompt loader。
7. Harness retry。

### 9.2 集成测试

覆盖：

1. 材料接口。
2. 简历创建和解析。
3. JD 创建和解析。
4. 备战包生成。
5. 题库查询。
6. 单题评分。
7. Agent run 查询。

### 9.3 端到端测试

主流程：

```text
POST /documents/text 创建简历材料
POST /documents/text 创建 JD 材料
POST /resumes 创建简历
POST /jobs 创建 JD
POST /resumes/{id}/parse
POST /jobs/{id}/parse
POST /prep-packages 生成题库
GET /prep-packages/{id}/questions 查询题库
POST /evaluations 提交答案
GET /evaluations/{id} 查询评价
GET /agent-runs/{id} 查询日志
```

验收断言：

1. 题库不少于 25 道。
2. 三个模块每个不少于 8 道。
3. 单题评价总分在 0 到 100。
4. 分项评分不超过各自满分。
5. 改进版回答存在。
6. 至少有 1 个追问。
7. Agent 日志存在。

## 10. 风险与处理

### 10.1 Agent 输出不满足 Schema

处理：

1. Pydantic 校验。
2. 自动重试一次。
3. 仍失败则记录 `agent_runs.failed`。
4. API 返回 `AGENT_FAILED`。

### 10.2 题库数量不达标

处理：

1. QuestionBank Schema 校验失败。
2. 带错误原因重试一次。
3. 测试覆盖 24 道题失败场景。

### 10.3 编造用户经历

处理：

1. Prompt 明确禁止。
2. 每题要求 `source_refs`。
3. 项目深挖题检查是否引用 resume source。
4. mock/e2e 样例中加入项目追问断言。

### 10.4 同步生成耗时过长

处理：

1. 第一版同步生成。
2. 保留 `status`。
3. 建议超时 120 秒。
4. 后续再引入异步任务。

### 10.5 敏感信息进入日志

处理：

1. `agent_runs.input_summary_json` 保存摘要。
2. 手机号、邮箱在 Agent 输入和日志摘要中脱敏。
3. 默认不保存完整 Prompt 和模型响应。

## 11. 推荐实现顺序

第一批：

1. 项目脚手架。
2. 配置、日志、request_id。
3. 统一响应和错误。
4. 通用 Schema。
5. 文本 hash 和脱敏工具。

第二批：

1. 数据库连接。
2. ORM 模型。
3. Alembic 迁移。
4. 默认用户。

第三批：

1. LLMClient。
2. mock Agent。
3. Harness。
4. Prompt loader。
5. Agent run 日志。

第四批：

1. 材料接口。
2. 简历创建与解析。
3. JD 创建与解析。
4. 可选面经创建与解析。

第五批：

1. Matching Agent。
2. Question Bank Agent。
3. 备战包生成接口。
4. 题库查询接口。

第六批：

1. Answer Evaluator Agent。
2. Memory Agent。
3. 单题评分接口。
4. 历史评分查询。

第七批：

1. 固定样例。
2. 单元测试。
3. 集成测试。
4. e2e 测试。

## 12. 完成定义

本 feature 完成时，应满足：

1. 用户可以输入简历、JD 和准备目标。
2. 系统可以生成 `ResumeProfile` 和 `JDProfile`。
3. 系统可以生成不少于 25 道岗位相关面试问题。
4. 三个题目模块每个不少于 8 道。
5. 系统可以推荐先练 3 道题。
6. 用户可以提交题库题目答案。
7. 用户可以提交自定义题目答案。
8. 系统可以生成结构化 `AnswerEvaluation`。
9. 系统可以保存评分记录。
10. 系统可以记录 Agent run 和 step。
11. mock Agent 可跑通完整闭环。
12. 单元、集成、端到端测试通过。
