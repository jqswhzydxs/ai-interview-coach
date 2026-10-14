# 第一阶段 MVP 实现计划 v0.1

## 1. 计划来源

本实现计划基于以下已存在文档整理：

1. `docs/02-agent-system-design-v0.1.md`
2. `docs/05-database-schema-design-v0.1.md`
3. `docs/08-api-design-v0.1.md`
4. `docs/09-pydantic-schema-design-v0.1.md`
5. `docs/10-agent-prompts-and-routing-v0.1.md`

计划原则：

1. 只覆盖第一阶段 MVP 已确定范围。
2. 优先实现完整面试备战包生成和单题模拟回答评分两条主线。
3. 先完成后端 API、数据模型、Schema、Harness 和 Markdown 报告导出。
4. 不引入自动联网搜索、登录注册、实时语音、支付、正式前端等后置能力。

## 2. 总体实现顺序

推荐按以下里程碑推进：

```text
M1 项目脚手架与基础配置
M2 数据库模型与 Alembic 迁移
M3 Pydantic Schema 与通用响应模型
M4 材料上传、文本保存与文件解析
M5 简历、JD、面经结构化解析
M6 轻量 Harness 与 Agent 运行日志
M7 完整面试备战包生成
M8 单题模拟回答评分
M9 Markdown 报告导出
M10 记忆更新、基础校验与验收样例
```

## 3. 已由文档确定的内容

### 3.0 本轮已确认实现决策

根据当前确认，第一阶段 MVP 按以下工程决策执行：

1. Python 版本使用 Python 3.11。
2. 包管理使用 `uv + pyproject.toml`。
3. Agent 第一轮先用 mock/stub 打通 API、数据库、Schema、报告导出闭环，同时预留真实 LLM 接口。
4. LLM Provider 使用国产模型方向，优先适配 DeepSeek 或 Kimi，具体模型名称通过 `LLM_MODEL` 环境变量配置。
5. LLM 调用层抽象为 `LLMClient`，避免业务代码直接绑定某一家模型 API。
6. 备战包生成第一版采用同步接口，同时保留 `status` 和 `agent_run_id`，方便后续改异步。
7. 默认用户由应用启动时检查并创建。
8. 第一轮暂不建 `interview_reviews` 和 `quality_evaluations` 表。
9. 第一版做手机号、邮箱的简单脱敏，尤其避免完整敏感信息进入 Agent 日志。
10. Prompt 正文独立文件化，放在 `app/agents/prompts/*.md`，文件名包含版本号。
11. 开发环境可配置保存完整 Prompt 和模型响应；默认只保存摘要。
12. Memory Agent 采用高置信度自动写入、低置信度仅保存建议的策略。
13. 同类问题连续低分，或证据明确且置信度高时，才写入长期薄弱点。
14. 第一版实现简单 `request_id` 中间件。
15. 查询接口分页使用 `limit + offset`。
16. 文件上传大小限制为 5MB。
17. Markdown 报告每次导出生成新文件，文件名包含 `prep_package_id` 和时间戳。
18. 第一版建立 2 到 3 组固定验收样例，用于验证 Schema、题量、评分字段和报告结构。

### 3.1 技术方向

已确定：

1. 后端框架使用 FastAPI。
2. ORM 使用 SQLAlchemy 2.x。
3. 数据库迁移使用 Alembic。
4. 数据库使用 PostgreSQL。
5. 数据校验使用 Pydantic v2。
6. 第一版不做正式前端。
7. 第一版使用本地文件存储。
8. 第一版导出 Markdown 报告。
9. Agent 编排先实现轻量 Harness，不强绑定 OpenAI Agents SDK 或 LangGraph。

仍需确认：

1. 本地开发数据库连接方式和默认数据库名是否沿用文档示例。
2. DeepSeek 与 Kimi 中优先接入哪一个作为默认 Provider。
3. 国产模型 API 的鉴权环境变量命名，例如 `DEEPSEEK_API_KEY`、`KIMI_API_KEY`。
4. 具体默认模型名称。

### 3.2 核心工作流

已确定：

1. 完整面试备战包生成。
2. 单题模拟回答评分。
3. 简历、JD、可选面经作为备战包输入。
4. 单题评分需要结合题目、用户回答、简历画像、JD 画像和评分锚点。
5. Memory Agent 负责根据评分结果提出长期记忆更新。

仍需确认：

1. 真实面试转写复盘是否在第一阶段只保留接口和表设计，还是同步实现基础版。

### 3.3 数据库范围

已确定第一版建议必建：

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

已确定可延后：

1. `interview_reviews`
2. `quality_evaluations`

仍需确认：

1. 文本 hash 使用算法，建议 SHA-256。
2. 脱敏后是否仍在 `source_documents.raw_text` 保留原文，或只对日志和 Agent 输入脱敏。

### 3.4 API 范围

已确定基础路径：

```text
/api/v1
```

已确定接口模块：

1. 材料接口：上传文件、粘贴文本。
2. 简历接口：创建简历、解析简历。
3. JD 接口：创建 JD、解析 JD。
4. 面经接口：创建面经、解析面经。
5. 备战包接口：生成、查询详情、查询题库、导出 Markdown。
6. 单题评分接口：提交回答、查询评分详情、查询历史评分。
7. Agent 运行日志接口：查询运行详情。

已确定第一版不做：

1. 登录注册接口。
2. 删除账号。
3. 在线支付。
4. 自动联网搜索面经。
5. 真实语音上传转写。
6. PDF 导出。

仍需确认：

1. 错误码枚举。
2. 备战包生成接口超时时间。

### 3.5 Schema 范围

已确定核心 Schema：

1. `EvidenceRef`
2. `ScoreItem`
3. `ActionItem`
4. `ResumeProfile`
5. `JDProfile`
6. `ExperienceProfile`
7. `MatchReport`
8. `InterviewQuestion`
9. `QuestionBank`
10. `PrepManual`
11. `InterviewPrepPackage`
12. `AnswerEvaluation`
13. `MemoryItem`

已确定约束：

1. `QuestionBank.total_count >= 25`。
2. 三个题目模块每个不少于 8 道。
3. 同一个题库内 `question_id` 唯一。
4. `PrepManual.bonus_points` 不少于 8 条。
5. `PrepManual.red_flags` 不少于 6 条。
6. `AnswerEvaluation` 总分 100 分。
7. 分项评分为：相关性 20、技术准确性 25、项目具体性 20、结构性 15、表达力 10、风险控制 10。
8. Agent 输出建议带 `schema_version`、`generated_at`、`agent_name`、`prompt_version`。

仍需确认：

1. Schema 文件拆分方式是否完全按业务对象拆分。
2. API 请求响应 Schema 是否与 Agent 输出 Schema 分离。
3. `EvidenceRef.quote` 是否保存原文片段，还是只保存摘要以减少敏感信息暴露。

### 3.6 Prompt 与路由

已确定 Prompt 版本命名：

1. `resume_analyzer_v0.1`
2. `jd_analyzer_v0.1`
3. `experience_analyzer_v0.1`
4. `matching_agent_v0.1`
5. `question_bank_agent_v0.1`
6. `prep_manual_agent_v0.1`
7. `answer_evaluator_v0.1`
8. `memory_agent_v0.1`

已确定备战包路由：

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
generate_prep_manual
↓
assemble_interview_prep_package
↓
render_markdown
```

已确定单题评分路由：

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

已确定失败处理：

1. schema 校验失败自动重试一次。
2. 数量不达标带错误原因重试一次。
3. 内容疑似编造时标记为需要人工检查或降级输出。
4. 多次失败时保存失败状态到 `agent_runs` 并返回明确错误。

仍需确认：

1. 降级输出的具体格式。
2. 内容疑似编造的自动检测规则。

## 4. 里程碑实施计划

### M1 项目脚手架与基础配置

目标：

1. 建立 FastAPI 项目结构。
2. 建立基础配置、日志和健康检查。
3. 准备本地开发环境变量。

主要任务：

1. 创建 `app/`、`app/api/v1/routes/`、`app/core/`、`app/db/`、`app/schemas/`、`app/services/`、`app/agents/`、`app/tools/`。
2. 创建 `pyproject.toml`。
3. 创建 `.env.example`。
4. 实现 `app/main.py`。
5. 实现 `/health`。
6. 配置基础日志。

已确定：

1. 项目结构已有文档建议。
2. `.env.example` 字段已有建议。
3. 第一版默认用户 ID 已有建议值。

仍需确认：

1. 是否马上配置测试框架。

### M2 数据库模型与 Alembic 迁移

目标：

1. 建立 PostgreSQL 连接。
2. 实现 SQLAlchemy ORM 模型。
3. 生成第一版 Alembic 迁移。

主要任务：

1. 实现 `app/db/session.py`。
2. 实现 `app/db/base.py`。
3. 按数据库设计创建 ORM 模型。
4. 配置 Alembic。
5. 生成初始迁移。
6. 准备默认用户 seed 方案。

已确定：

1. 数据库使用 PostgreSQL。
2. 必建表范围已明确。
3. 大量 Agent 输出使用 JSONB。
4. 本地文件路径和提取文本需要入库。

仍需确认：

1. 是否为 JSONB 高频字段第一版就建 GIN 索引。

### M3 Pydantic Schema 与通用响应模型

目标：

1. 实现核心业务 Schema。
2. 实现 API 请求响应 Schema。
3. 实现 Agent 输出校验基础能力。

主要任务：

1. 实现通用 `EvidenceRef`、`ScoreItem`、`ActionItem`。
2. 实现 `ResumeProfile`、`JDProfile`、`ExperienceProfile`。
3. 实现 `MatchReport`、`InterviewQuestion`、`QuestionBank`、`PrepManual`。
4. 实现 `InterviewPrepPackage`、`AnswerEvaluation`、`MemoryItem`。
5. 增加 Pydantic 数量约束和分数约束。
6. 实现统一 API 响应模型。

已确定：

1. 核心字段已由 Schema 文档定义。
2. 题量、手册数量、评分维度已确定。
3. 展示顺序已确定。

仍需确认：

1. API Schema 和 Agent Schema 的复用边界。
2. 是否对所有 Agent 输出统一包一层元信息。

### M4 材料上传、文本保存与文件解析

目标：

1. 支持上传 PDF、DOCX、Markdown。
2. 支持粘贴文本。
3. 统一保存到 `source_documents`。

主要任务：

1. 实现 `POST /api/v1/documents/upload`。
2. 实现 `POST /api/v1/documents/text`。
3. 实现文件类型识别。
4. 实现 PDF 文本提取。
5. 实现 DOCX 文本提取。
6. 实现 Markdown 和纯文本处理。
7. 计算文本 hash。
8. 保存文件路径、正文和元信息。

已确定：

1. 简历支持 PDF、DOCX、Markdown、纯文本。
2. JD 和面经支持粘贴文本。
3. 上传文件保存本地，数据库保存路径和提取文本。

仍需确认：

1. `storage/uploads` 和 `storage/reports` 作为固定目录时，是否允许通过环境变量覆盖。
2. 脱敏策略作用范围：仅日志和 Agent 输入，还是数据库原文也脱敏。

### M5 简历、JD、面经结构化解析

目标：

1. 创建简历、JD、面经业务记录。
2. 调用对应 Agent 生成结构化 Profile。

主要任务：

1. 实现 `POST /api/v1/resumes`。
2. 实现 `POST /api/v1/resumes/{resume_id}/parse`。
3. 实现 `POST /api/v1/jobs`。
4. 实现 `POST /api/v1/jobs/{job_description_id}/parse`。
5. 实现 `POST /api/v1/experiences`。
6. 实现 `POST /api/v1/experiences/{interview_experience_id}/parse`。
7. 保存 `resume_profiles`、`jd_profiles`、`experience_profiles`。

已确定：

1. 三类解析 Agent 的职责和输出 Schema 已明确。
2. 解析结果需要关联 `agent_run_id`。
3. 面经是可选增强材料。

仍需确认：

1. 解析接口是否同步返回完整 profile。
2. 解析失败时是否允许创建业务记录但无 profile。

### M6 轻量 Harness 与 Agent 运行日志

目标：

1. 实现 Harness 调度框架。
2. 记录 Agent 工作流运行和步骤。
3. 对 Agent 输出做 Schema 校验和重试。

主要任务：

1. 实现 `app/agents/base.py`。
2. 实现 `app/agents/harness.py`。
3. 实现 Agent 调用接口。
4. 实现 `agent_runs` 创建、状态更新和失败记录。
5. 实现 `agent_run_steps` 记录。
6. 实现 schema 校验失败重试一次。
7. 实现 `GET /api/v1/agent-runs/{agent_run_id}`。

已确定：

1. Harness 负责调度、状态、日志、校验、重试、入库。
2. Harness 不负责具体内容生成。
3. 失败处理策略已有初版定义。

仍需确认：

1. 降级输出策略。
2. DeepSeek 或 Kimi 的 API 适配细节。

### M7 完整面试备战包生成

目标：

1. 打通完整面试备战包生成工作流。
2. 生成差距分析、题库、备战手册、推荐先练 3 题和行动清单。

主要任务：

1. 实现 Matching Agent。
2. 实现 Question Bank Agent。
3. 实现 Prep Manual Agent。
4. 实现 `POST /api/v1/prep-packages`。
5. 实现 `GET /api/v1/prep-packages/{prep_package_id}`。
6. 实现 `GET /api/v1/prep-packages/{prep_package_id}/questions`。
7. 保存 `interview_prep_packages`。
8. 保存 `match_reports`。
9. 保存 `interview_questions`。
10. 保存 `prep_manuals`。
11. 保存 `recommended_questions`。

已确定：

1. 备战包展示顺序已确定。
2. 题库数量和模块约束已确定。
3. 每道题字段已确定。
4. 手册加分点和雷点数量已确定。
5. 推荐先练 3 道题已确定。

仍需确认：

1. 推荐先练 3 题的选择规则。
2. 备战包 title 默认生成规则。

### M8 单题模拟回答评分

目标：

1. 支持用户提交题目回答。
2. 生成评分报告、改进版回答、追问和下一题建议。
3. 生成记忆更新建议。

主要任务：

1. 实现 Answer Evaluator Agent。
2. 实现 Memory Agent 基础版。
3. 实现 `POST /api/v1/evaluations`。
4. 实现 `GET /api/v1/evaluations/{answer_evaluation_id}`。
5. 实现 `GET /api/v1/evaluations`。
6. 保存 `answer_evaluations`。
7. 根据 `memory_update` 写入或更新 `memory_items`。

已确定：

1. 单题评分总分 100。
2. 分项评分权重已确定。
3. 评分输出字段已确定。
4. 支持题库题目和用户手动题目。

仍需确认：

1. 高置信度自动写入的阈值。

### M9 Markdown 报告导出

目标：

1. 将完整备战包渲染为 Markdown。
2. 保存到本地报告目录。
3. 支持 API 返回路径和 Markdown 内容。

主要任务：

1. 实现 `app/tools/markdown_renderer.py`。
2. 实现 `POST /api/v1/prep-packages/{prep_package_id}/export/markdown`。
3. 写入 `storage/reports`。
4. 更新 `interview_prep_packages.rendered_markdown`。

已确定：

1. 第一版支持 Markdown 报告导出。
2. PDF 导出不在第一版。
3. 报告展示顺序已确定。

仍需确认：

1. 报告文件名中时间戳格式。

### M10 记忆更新、基础校验与验收样例

目标：

1. 用固定样例验证核心闭环。
2. 检查结构化输出是否满足数量和字段约束。
3. 验证日志、记忆和报告导出链路。

主要任务：

1. 准备简历样例。
2. 准备 JD 样例。
3. 准备可选面经样例。
4. 准备单题回答样例。
5. 编写单元测试覆盖 Schema 约束。
6. 编写集成测试覆盖备战包生成。
7. 编写集成测试覆盖单题评分。
8. 检查 `agent_runs` 与 `agent_run_steps` 是否完整记录。

已确定：

1. 输出格式评测维度已由系统设计文档定义。
2. 内容质量评测维度已由系统设计文档定义。
3. 用户价值指标已有初版定义。

仍需确认：

1. 固定验收样例的具体数量和样例内容。
2. 测试是否允许使用 mock Agent 固定输出。

## 5. 推荐开发切片

### 5.1 第一条可运行闭环

优先打通：

```text
粘贴纯文本简历
↓
粘贴 JD
↓
创建简历和 JD
↓
mock 或真实 Agent 生成 ResumeProfile 和 JDProfile
↓
生成备战包
↓
查询备战包
↓
导出 Markdown
```

原因：

1. 不依赖文件上传复杂度。
2. 可以尽早验证数据库、Schema、Harness、API 和报告结构。
3. 后续再补 PDF、DOCX 解析。

### 5.2 第二条可运行闭环

继续打通：

```text
选择备战包中的一道题
↓
提交用户回答
↓
生成 AnswerEvaluation
↓
写入 answer_evaluations
↓
生成 memory_update
↓
查询历史评分
```

原因：

1. 这是第一阶段 MVP 的第二条核心工作流。
2. 可以验证题目评分锚点、简历/JD 上下文和记忆更新是否能串起来。

### 5.3 第三条增强闭环

最后补齐：

```text
上传 PDF / DOCX 简历
↓
提取文本
↓
保存 source_documents
↓
复用已有解析和备战包流程
```

原因：

1. 文件解析属于输入增强。
2. 核心业务链路可以先用文本输入验证。

## 6. 风险与处理

### 6.1 Agent 输出不稳定

风险：

1. 字段缺失。
2. 题量不达标。
3. 分数不符合范围。
4. 输出中混入自由文本。

处理：

1. Pydantic 校验。
2. 带错误原因重试一次。
3. 失败写入 `agent_runs`。
4. 返回明确错误信息。

### 6.2 内容编造

风险：

1. 编造用户没有写过的项目。
2. 编造成果数据。
3. 把面经说成确定真题。

处理：

1. Prompt 边界明确禁止。
2. 要求 evidence_refs。
3. 对项目题检查是否引用简历项目。
4. 疑似编造时标记人工检查或降级输出。

### 6.3 生成耗时过长

风险：

1. 备战包生成涉及多个 Agent。
2. 同步接口可能超时。

处理：

1. 第一版可先同步实现。
2. 保留 `status` 字段。
3. 后续可切换为异步任务。

仍需确认：

1. 同步接口可接受的最长等待时间。

### 6.4 敏感信息存储

风险：

1. 简历、JD、面经、回答中可能包含个人信息。
2. 日志中可能保存过多原文。

处理：

1. `agent_runs.input_summary_json` 只保存摘要。
2. 原始材料集中保存在 `source_documents`。
3. 后续可加入脱敏策略。

仍需确认：

1. 是否只对日志和 Agent 输入脱敏，还是数据库原始正文也脱敏。

## 7. 当前最小可执行任务清单

建议先从以下任务开始：

1. 创建 FastAPI 项目结构。
2. 配置 `pyproject.toml` 和 `.env.example`。
3. 实现 `/health`。
4. 配置 SQLAlchemy、PostgreSQL 和 Alembic。
5. 建立 MVP 必建表的 ORM 模型。
6. 实现核心 Pydantic Schema。
7. 实现粘贴文本材料接口。
8. 实现简历、JD 创建接口。
9. 实现 mock Agent Harness，先返回符合 Schema 的固定结构。
10. 打通备战包生成和查询接口。

## 8. 待确认问题汇总

### 8.1 工程配置

1. 测试框架是否第一步引入。
2. DeepSeek 与 Kimi 中默认接入哪一个。
3. 国产模型具体默认模型名称。
4. 国产模型 API key 环境变量命名。

### 8.2 数据与存储

1. `storage/uploads` 和 `storage/reports` 是否允许通过环境变量覆盖。
2. 手机号、邮箱脱敏是否作用于数据库原文。
3. 文本 hash 是否使用 SHA-256。

### 8.3 Agent 实现

1. DeepSeek / Kimi API 适配细节。
2. 内容疑似编造的自动检测规则。
3. 降级输出的具体格式。

### 8.4 API 行为

1. 错误码枚举。
2. 备战包同步生成接口的超时时间。

### 8.5 记忆与评测

1. 高置信度自动写入记忆的阈值。
2. 固定验收样例的具体内容。

## 9. 第一阶段完成定义

第一阶段 MVP 可以认为完成，当且仅当：

1. 用户可以提交简历和 JD。
2. 系统可以生成并保存结构化简历画像和 JD 画像。
3. 用户可以可选提交面经。
4. 系统可以生成完整面试备战包。
5. 备战包包含差距分析、不少于 25 道题、备战手册、推荐先练 3 题和行动清单。
6. 用户可以选择题目并提交回答。
7. 系统可以生成 100 分制单题评分报告。
8. 系统可以给出改进版回答、追问和下一题建议。
9. 系统可以保存 Agent 运行日志。
10. 系统可以提出或保存薄弱点记忆更新。
11. 系统可以导出 Markdown 报告。
12. 明确排除的第一阶段外功能没有被误引入。
