# 第一阶段 MVP Tasks v0.1

## 1. 任务拆解原则

本任务清单基于：

1. `docs/13-first-phase-mvp-feature-spec-v0.1.md`
2. `docs/14-first-phase-mvp-implementation-plan-v0.1.md`

拆解原则：

1. 每个任务都应可以单独实现、单独提交、单独验证。
2. 每个任务都包含目标文件路径、验收标准和测试方式。
3. 第一轮使用 mock/stub Agent 打通闭环，同时预留真实 LLM 接口。
4. 第一阶段不实现登录注册、正式前端、自动联网搜索、实时语音、支付、PDF 导出。
5. Python 使用 3.11，包管理使用 `uv + pyproject.toml`。
6. 数据库使用 PostgreSQL，ORM 使用 SQLAlchemy 2.x，迁移使用 Alembic。
7. Pydantic 使用 v2。

## 2. 任务总览

| ID | 任务 | 阶段 | 依赖 |
| --- | --- | --- | --- |
| T001 | 创建项目脚手架与基础配置 | M1 | 无 |
| T002 | 配置应用设置、环境变量和日志 | M1 | T001 |
| T003 | 实现 FastAPI 应用入口与健康检查 | M1 | T001, T002 |
| T004 | 配置数据库连接与 SQLAlchemy Base | M2 | T002 |
| T005 | 配置 Alembic 迁移框架 | M2 | T004 |
| T006 | 实现用户、材料、简历、JD、面经模型 | M2 | T004 |
| T007 | 实现备战包、题库、评分、记忆、Agent 日志模型 | M2 | T006 |
| T008 | 生成并验证初始数据库迁移 | M2 | T005, T006, T007 |
| T009 | 实现默认用户初始化 | M2 | T006 |
| T010 | 实现通用 Pydantic Schema | M3 | T001 |
| T011 | 实现材料、简历、JD、面经 Schema | M3 | T010 |
| T012 | 实现备战包、题库、手册 Schema | M3 | T010 |
| T013 | 实现单题评分、记忆和 Agent 日志 Schema | M3 | T010 |
| T014 | 实现统一 API 响应、错误模型和 request_id | M3 | T002, T010 |
| T015 | 实现文本脱敏、hash 和分页工具 | M3 | T002 |
| T016 | 实现文件解析工具 | M4 | T015 |
| T017 | 实现材料上传和文本保存接口 | M4 | T006, T011, T014, T016 |
| T018 | 实现简历创建与解析接口 | M5 | T017, T019 |
| T019 | 实现 mock Agent 基类与 LLMClient 抽象 | M6 | T010, T013 |
| T020 | 实现 Harness 与 Agent 运行日志 | M6 | T007, T013, T019 |
| T021 | 实现 JD 创建与解析接口 | M5 | T017, T020 |
| T022 | 实现面经创建与解析接口 | M5 | T017, T020 |
| T023 | 实现 Prompt 文件结构与版本加载 | M6 | T019 |
| T024 | 实现备战包生成服务 | M7 | T018, T021, T022, T020 |
| T025 | 实现备战包 API | M7 | T024, T014 |
| T026 | 实现题库查询 API | M7 | T024, T025 |
| T027 | 实现 Markdown 报告渲染与导出 | M9 | T024, T025 |
| T028 | 实现单题评分服务 | M8 | T024, T020 |
| T029 | 实现单题评分 API | M8 | T028, T014 |
| T030 | 实现记忆写入策略 | M8 | T028 |
| T031 | 实现 Agent 运行日志查询 API | M6 | T020, T014 |
| T032 | 准备固定验收样例 | M10 | T011, T012, T013 |
| T033 | 编写 Schema 单元测试 | M10 | T010, T011, T012, T013 |
| T034 | 编写 API 集成测试 | M10 | T017, T025, T029 |
| T035 | 编写端到端 MVP 验收测试 | M10 | T027, T029, T032 |

## 3. 详细任务

### T001 创建项目脚手架与基础配置

目标：

建立第一阶段后端项目的目录结构和 Python 项目元数据。

文件路径：

1. `pyproject.toml`
2. `.python-version`
3. `.gitignore`
4. `README.md`
5. `app/__init__.py`
6. `app/api/__init__.py`
7. `app/api/v1/__init__.py`
8. `app/api/v1/routes/__init__.py`
9. `app/core/__init__.py`
10. `app/db/__init__.py`
11. `app/db/models/__init__.py`
12. `app/schemas/__init__.py`
13. `app/services/__init__.py`
14. `app/agents/__init__.py`
15. `app/tools/__init__.py`
16. `tests/__init__.py`

验收标准：

1. 项目使用 Python 3.11。
2. `pyproject.toml` 包含 FastAPI、Uvicorn、SQLAlchemy、Alembic、Pydantic v2、pydantic-settings、psycopg、pytest、httpx 等基础依赖。
3. 目录结构与实现计划中的分层一致。
4. 不包含前端、登录注册、支付等第一阶段外目录。

测试方式：

1. 运行 `uv sync` 能成功创建环境。
2. 运行 `uv run python --version` 显示 Python 3.11.x。
3. 运行 `uv run python -c "import fastapi, sqlalchemy, pydantic"` 无报错。

### T002 配置应用设置、环境变量和日志

目标：

实现统一配置读取和基础日志配置。

文件路径：

1. `.env.example`
2. `app/core/config.py`
3. `app/core/logging.py`

验收标准：

1. `.env.example` 包含 `APP_ENV`、`APP_NAME`、`DATABASE_URL`、`UPLOAD_DIR`、`REPORT_DIR`、`DEFAULT_USER_ID`、`LLM_PROVIDER`、`LLM_MODEL`、`DEEPSEEK_API_KEY`、`KIMI_API_KEY`、`SAVE_FULL_LLM_LOGS`。
2. `config.py` 使用 Pydantic Settings 读取配置。
3. `UPLOAD_DIR` 默认 `storage/uploads`。
4. `REPORT_DIR` 默认 `storage/reports`。
5. `SAVE_FULL_LLM_LOGS` 默认关闭。
6. 日志配置能输出时间、级别、request_id 和消息。

测试方式：

1. 运行配置单元测试，验证默认值。
2. 设置临时环境变量后读取配置，确认覆盖生效。
3. 调用日志初始化函数，确认不会重复添加 handler。

### T003 实现 FastAPI 应用入口与健康检查

目标：

创建可启动的 FastAPI 应用和 `/health` 接口。

文件路径：

1. `app/main.py`
2. `app/api/v1/router.py`
3. `app/api/v1/routes/health.py`
4. `tests/integration/test_health.py`

验收标准：

1. 应用实例名为 `app`。
2. API 基础路径为 `/api/v1`。
3. `GET /api/v1/health` 返回应用名、环境和 `status=ok`。
4. 接口响应使用统一响应结构。

测试方式：

1. 运行 `uv run pytest tests/integration/test_health.py`。
2. 使用 FastAPI TestClient 请求 `/api/v1/health`，断言状态码为 200。
3. 断言返回 JSON 包含 `data.status == "ok"`。

### T004 配置数据库连接与 SQLAlchemy Base

目标：

建立数据库连接、Session 和 ORM Base。

文件路径：

1. `app/db/base.py`
2. `app/db/session.py`
3. `app/db/deps.py`
4. `tests/unit/test_db_config.py`

验收标准：

1. 支持从 `DATABASE_URL` 创建 SQLAlchemy engine。
2. 提供 `SessionLocal`。
3. 提供 FastAPI dependency `get_db`。
4. ORM Base 可被 Alembic 引用。

测试方式：

1. 单元测试验证 engine URL 来自配置。
2. 使用 SQLite 临时 URL 或测试 PostgreSQL URL 创建 session。
3. `get_db` dependency 能正常 yield 并关闭 session。

### T005 配置 Alembic 迁移框架

目标：

配置 Alembic，使其能读取项目 ORM metadata 和数据库配置。

文件路径：

1. `alembic.ini`
2. `alembic/env.py`
3. `alembic/versions/.gitkeep`

验收标准：

1. Alembic 能读取 `app.db.base.Base.metadata`。
2. Alembic 使用项目配置中的 `DATABASE_URL`。
3. `alembic upgrade head` 可执行。

测试方式：

1. 运行 `uv run alembic current` 不报配置错误。
2. 在测试数据库上运行 `uv run alembic upgrade head`。

### T006 实现用户、材料、简历、JD、面经模型

目标：

实现用户与材料层 ORM 模型。

文件路径：

1. `app/db/models/user.py`
2. `app/db/models/source_document.py`
3. `app/db/models/resume.py`
4. `app/db/models/job_description.py`
5. `app/db/models/interview_experience.py`
6. `app/db/models/__init__.py`
7. `tests/unit/test_models_materials.py`

验收标准：

1. 实现 `users`、`source_documents`、`resumes`、`resume_profiles`、`job_descriptions`、`jd_profiles`、`interview_experiences`、`experience_profiles`。
2. 主键使用 UUID。
3. 外键关系与数据库设计文档一致。
4. JSONB 字段用于结构化 profile。
5. 时间字段包含 `created_at`，需要更新的表包含 `updated_at`。

测试方式：

1. ORM metadata 包含上述表名。
2. 使用测试数据库创建表成功。
3. 插入用户、source document、resume、JD、experience 记录成功。

### T007 实现备战包、题库、评分、记忆、Agent 日志模型

目标：

实现 MVP 主链路 ORM 模型。

文件路径：

1. `app/db/models/prep_package.py`
2. `app/db/models/question.py`
3. `app/db/models/evaluation.py`
4. `app/db/models/memory.py`
5. `app/db/models/agent_run.py`
6. `app/db/models/__init__.py`
7. `tests/unit/test_models_workflow.py`

验收标准：

1. 实现 `interview_prep_packages`、`prep_package_experiences`、`match_reports`、`interview_questions`、`prep_manuals`、`recommended_questions`。
2. 实现 `answer_evaluations`、`memory_items`、`agent_runs`、`agent_run_steps`。
3. 不在第一轮实现 `interview_reviews` 和 `quality_evaluations`。
4. 题库、评分、手册和日志字段覆盖数据库设计文档中的 MVP 必需字段。
5. 唯一约束和常用索引按数据库设计文档实现。

测试方式：

1. ORM metadata 包含所有 MVP 表。
2. 插入备战包、题目、推荐题、评分、记忆、Agent 运行记录成功。
3. 验证 `prep_package_id + question_id` 唯一约束生效。

### T008 生成并验证初始数据库迁移

目标：

生成初始 Alembic 迁移并验证数据库结构。

文件路径：

1. `alembic/versions/*_initial_mvp_schema.py`
2. `tests/integration/test_migrations.py`

验收标准：

1. 迁移包含 MVP 必建表。
2. 迁移不包含 `interview_reviews` 和 `quality_evaluations`。
3. `alembic upgrade head` 后数据库表结构正确。
4. `alembic downgrade base` 可回滚。

测试方式：

1. 在测试数据库运行 `uv run alembic upgrade head`。
2. 查询数据库 information schema，确认表存在。
3. 运行 `uv run alembic downgrade base`，确认可回滚。

### T009 实现默认用户初始化

目标：

应用启动时检查并创建默认用户。

文件路径：

1. `app/db/init_db.py`
2. `app/main.py`
3. `tests/integration/test_default_user.py`

验收标准：

1. 默认用户 ID 来自 `DEFAULT_USER_ID`。
2. 应用启动时如果默认用户不存在，则创建。
3. 如果默认用户已存在，不重复创建。
4. 默认用户 role 为 `candidate`。

测试方式：

1. 清空测试数据库后调用初始化函数，断言用户存在。
2. 连续调用两次初始化函数，断言只有一条默认用户。

### T010 实现通用 Pydantic Schema

目标：

实现通用结构化对象。

文件路径：

1. `app/schemas/common.py`
2. `tests/unit/test_common_schemas.py`

验收标准：

1. 实现 `EvidenceRef`、`ScoreItem`、`ActionItem`。
2. `EvidenceRef.source_type` 限定为 `resume`、`jd`、`experience`、`answer`、`inferred`。
3. `ActionItem.priority` 限定为 `high`、`medium`、`low`。
4. `ScoreItem.score` 不允许大于 `max_score`。

测试方式：

1. 构造合法对象，断言通过。
2. 构造非法枚举值，断言 Pydantic 校验失败。
3. 构造 `score > max_score`，断言校验失败。

### T011 实现材料、简历、JD、面经 Schema

目标：

实现输入材料和 profile 相关 Schema。

文件路径：

1. `app/schemas/document.py`
2. `app/schemas/resume.py`
3. `app/schemas/job_description.py`
4. `app/schemas/experience.py`
5. `tests/unit/test_profile_schemas.py`

验收标准：

1. 实现材料上传、文本材料、简历创建、JD 创建、面经创建请求 Schema。
2. 实现 `ResumeProfile`、`JDProfile`、`ExperienceProfile`。
3. Profile 支持 `schema_version`、`generated_at`、`agent_name`、`prompt_version` 元信息。
4. 简历项目经历支持 evidence refs。

测试方式：

1. 使用固定样例构造三个 profile，断言校验通过。
2. 缺少必填字段时校验失败。
3. 枚举字段传非法值时校验失败。

### T012 实现备战包、题库、手册 Schema

目标：

实现完整备战包结构化 Schema。

文件路径：

1. `app/schemas/prep_package.py`
2. `app/schemas/question.py`
3. `app/schemas/prep_manual.py`
4. `tests/unit/test_prep_package_schemas.py`

验收标准：

1. 实现 `MatchReport`、`InterviewQuestion`、`QuestionBank`、`PrepManual`、`InterviewPrepPackage`。
2. `QuestionBank.total_count >= 25`。
3. 三个题目模块每个不少于 8 道。
4. 同一题库内 `question_id` 唯一。
5. `PrepManual.bonus_points >= 8`。
6. `PrepManual.red_flags >= 6`。
7. `InterviewPrepPackage` 字段顺序和展示顺序一致。

测试方式：

1. 使用 25 道题样例断言校验通过。
2. 使用 24 道题样例断言校验失败。
3. 使用重复 `question_id` 样例断言校验失败。
4. 使用少于 8 条加分点或少于 6 条雷点样例断言校验失败。

### T013 实现单题评分、记忆和 Agent 日志 Schema

目标：

实现评分、记忆和 Agent 运行相关 Schema。

文件路径：

1. `app/schemas/evaluation.py`
2. `app/schemas/memory.py`
3. `app/schemas/agent.py`
4. `tests/unit/test_evaluation_memory_schemas.py`

验收标准：

1. 实现 `AnswerEvaluation`。
2. 实现 `MemoryItem`。
3. 实现 Agent run 和 step 响应 Schema。
4. 分项评分满分分别为 20、25、20、15、10、10。
5. 总分范围为 0 到 100。

测试方式：

1. 构造合法评分结果，断言校验通过。
2. 构造分项得分超过满分，断言校验失败。
3. 构造非法 memory status，断言校验失败。

### T014 实现统一 API 响应、错误模型和 request_id

目标：

统一接口响应格式，并为日志和响应注入 request_id。

文件路径：

1. `app/schemas/response.py`
2. `app/core/errors.py`
3. `app/core/middleware.py`
4. `app/main.py`
5. `tests/integration/test_response_format.py`

验收标准：

1. 成功响应格式为 `{ "data": ..., "message": "ok", "request_id": "..." }`。
2. 错误响应格式为 `{ "error": { "code": "...", "message": "...", "details": {} } }`。
3. 每个请求都有 request_id。
4. request_id 出现在响应 header 或响应 body 中。

测试方式：

1. 请求 `/api/v1/health`，断言响应包含 request_id。
2. 发送非法请求，断言错误格式一致。
3. 检查日志中包含 request_id。

### T015 实现文本脱敏、hash 和分页工具

目标：

提供通用文本处理和分页能力。

文件路径：

1. `app/tools/text_utils.py`
2. `app/schemas/pagination.py`
3. `tests/unit/test_text_utils.py`

验收标准：

1. 文本 hash 使用 SHA-256。
2. 支持手机号脱敏。
3. 支持邮箱脱敏。
4. 分页参数使用 `limit + offset`。
5. `limit` 有合理最大值，建议最大 100。

测试方式：

1. 同一文本 hash 稳定一致。
2. 手机号和邮箱被替换为脱敏形式。
3. 非敏感文本不被破坏。
4. 非法分页参数校验失败。

### T016 实现文件解析工具

目标：

支持 PDF、DOCX、Markdown、纯文本解析。

文件路径：

1. `app/tools/file_parser.py`
2. `tests/unit/test_file_parser.py`
3. `tests/fixtures/files/sample_resume.md`
4. `tests/fixtures/files/sample_resume.txt`
5. `tests/fixtures/files/sample_resume.docx`
6. `tests/fixtures/files/sample_resume.pdf`

验收标准：

1. PDF 使用 PyMuPDF 提取文本。
2. DOCX 使用 python-docx 提取文本。
3. Markdown 和纯文本按文本读取。
4. 文件大小限制为 5MB。
5. 不支持的文件类型返回明确错误。

测试方式：

1. 分别解析四类样例文件，断言返回非空文本。
2. 上传超过 5MB 的测试文件，断言拒绝。
3. 上传不支持扩展名，断言错误码正确。

### T017 实现材料上传和文本保存接口

目标：

实现 `source_documents` 入库能力。

文件路径：

1. `app/api/v1/routes/documents.py`
2. `app/services/document_service.py`
3. `app/api/v1/router.py`
4. `tests/integration/test_documents_api.py`

验收标准：

1. 实现 `POST /api/v1/documents/upload`。
2. 实现 `POST /api/v1/documents/text`。
3. 支持 `document_type=resume|jd|interview_experience`。
4. 上传文件保存到 `UPLOAD_DIR`。
5. 粘贴文本和提取文本保存到 `source_documents.raw_text`。
6. 入库时保存 `text_hash` 和 metadata。

测试方式：

1. 调用文本接口创建 JD，断言返回 `source_document_id`。
2. 上传 Markdown 简历，断言文件落盘且数据库有记录。
3. 上传不支持 document_type，断言校验失败。

### T018 实现简历创建与解析接口

目标：

支持创建简历业务记录并生成 ResumeProfile。

文件路径：

1. `app/api/v1/routes/resumes.py`
2. `app/services/resume_service.py`
3. `app/agents/resume_analyzer.py`
4. `app/api/v1/router.py`
5. `tests/integration/test_resumes_api.py`

验收标准：

1. 实现 `POST /api/v1/resumes`。
2. 实现 `POST /api/v1/resumes/{resume_id}/parse`。
3. 简历必须关联 `source_document_id`。
4. parse 接口通过 Harness 生成 mock `ResumeProfile`。
5. 解析结果保存到 `resume_profiles`。
6. 响应包含 `resume_profile_id`、`agent_run_id` 和 `profile`。

测试方式：

1. 使用已创建的 source document 创建 resume。
2. 调用 parse，断言返回 profile。
3. 查询数据库，断言 `resume_profiles` 和 `agent_runs` 有记录。

### T019 实现 mock Agent 基类与 LLMClient 抽象

目标：

建立 Agent 抽象层，先支持 mock/stub，预留 DeepSeek/Kimi。

文件路径：

1. `app/agents/base.py`
2. `app/agents/llm_client.py`
3. `app/agents/mock_client.py`
4. `tests/unit/test_agent_base.py`

验收标准：

1. 定义统一 Agent 输入输出接口。
2. 定义 `LLMClient` 抽象。
3. 实现 `MockLLMClient`。
4. 配置支持 `LLM_PROVIDER=mock|deepseek|kimi`。
5. DeepSeek/Kimi 可先保留适配类骨架，不在本任务要求真实调用成功。

测试方式：

1. 使用 mock client 调用，返回固定结构。
2. 非法 provider 配置时抛出明确错误。
3. Agent 基类能记录 agent name 和 prompt version。

### T020 实现 Harness 与 Agent 运行日志

目标：

实现 Agent 调度、日志记录、Schema 校验和重试基础能力。

文件路径：

1. `app/agents/harness.py`
2. `app/services/agent_run_service.py`
3. `tests/unit/test_harness.py`

验收标准：

1. Harness 能创建 `agent_runs`。
2. 每个 Agent 调用能创建 `agent_run_steps`。
3. Agent 成功时 run 状态为 `succeeded`。
4. Agent 失败时 run 状态为 `failed` 并保存错误信息。
5. Schema 校验失败时自动重试一次。
6. 默认只保存输入输出摘要。

测试方式：

1. 使用 mock Agent 成功执行，断言 run 和 step 记录存在。
2. 使用故意返回非法结构的 mock Agent，断言重试发生。
3. 重试后仍失败时，断言 run 状态为 failed。

### T021 实现 JD 创建与解析接口

目标：

支持创建 JD 并生成 JDProfile。

文件路径：

1. `app/api/v1/routes/jobs.py`
2. `app/services/job_service.py`
3. `app/agents/jd_analyzer.py`
4. `app/api/v1/router.py`
5. `tests/integration/test_jobs_api.py`

验收标准：

1. 实现 `POST /api/v1/jobs`。
2. 实现 `POST /api/v1/jobs/{job_description_id}/parse`。
3. 创建 JD 时保存 raw_text。
4. parse 接口通过 Harness 生成 mock `JDProfile`。
5. 解析结果保存到 `jd_profiles`。

测试方式：

1. 创建 JD，断言返回 `job_description_id`。
2. 调用 parse，断言返回 `jd_profile_id`。
3. 查询数据库，断言 `jd_profiles` 和 `agent_runs` 有记录。

### T022 实现面经创建与解析接口

目标：

支持可选面经材料入库和结构化解析。

文件路径：

1. `app/api/v1/routes/experiences.py`
2. `app/services/experience_service.py`
3. `app/agents/experience_analyzer.py`
4. `app/api/v1/router.py`
5. `tests/integration/test_experiences_api.py`

验收标准：

1. 实现 `POST /api/v1/experiences`。
2. 实现 `POST /api/v1/experiences/{interview_experience_id}/parse`。
3. 支持 `online_shared`、`self_history`、`written_test`、`interview_transcript` 类型。
4. 解析结果保存到 `experience_profiles`。
5. 没有面经不影响后续备战包生成。

测试方式：

1. 创建面经，断言返回 ID。
2. 调用 parse，断言返回 `experience_profile_id`。
3. 不提供面经时生成备战包测试仍能通过。

### T023 实现 Prompt 文件结构与版本加载

目标：

将 Prompt 版本文件化管理。

文件路径：

1. `app/agents/prompts/resume_analyzer_v0.1.md`
2. `app/agents/prompts/jd_analyzer_v0.1.md`
3. `app/agents/prompts/experience_analyzer_v0.1.md`
4. `app/agents/prompts/matching_agent_v0.1.md`
5. `app/agents/prompts/question_bank_agent_v0.1.md`
6. `app/agents/prompts/prep_manual_agent_v0.1.md`
7. `app/agents/prompts/answer_evaluator_v0.1.md`
8. `app/agents/prompts/memory_agent_v0.1.md`
9. `app/agents/prompt_loader.py`
10. `tests/unit/test_prompt_loader.py`

验收标准：

1. Prompt 文件名包含版本号。
2. Prompt loader 能按名称加载 Prompt。
3. 缺失 Prompt 文件时返回明确错误。
4. Prompt 边界包含不编造经历、不虚构学历、不把面经当真题、输出证据引用。

测试方式：

1. 加载每个 Prompt 文件，断言内容非空。
2. 加载不存在的 Prompt，断言抛出指定异常。

### T024 实现备战包生成服务

目标：

打通完整面试备战包生成服务层。

文件路径：

1. `app/services/prep_package_service.py`
2. `app/agents/matching_agent.py`
3. `app/agents/question_bank_agent.py`
4. `app/agents/prep_manual_agent.py`
5. `tests/integration/test_prep_package_service.py`

验收标准：

1. 输入 resume_id、job_description_id、可选 interview_experience_ids。
2. 自动加载或生成 `ResumeProfile` 和 `JDProfile`。
3. 可选加载 `ExperienceProfile`。
4. 生成并保存 `interview_prep_packages`。
5. 保存 `match_reports`。
6. 保存不少于 25 道 `interview_questions`。
7. 三个题目模块每个不少于 8 道。
8. 保存 `prep_manuals`，加分点不少于 8 条，雷点不少于 6 条。
9. 保存 3 条 `recommended_questions`。

测试方式：

1. 使用 mock Agent 固定输出生成备战包。
2. 断言数据库中备战包状态为 `ready`。
3. 断言题库数量和模块数量满足约束。
4. 断言推荐题数量为 3。

### T025 实现备战包 API

目标：

提供备战包生成和详情查询接口。

文件路径：

1. `app/api/v1/routes/prep_packages.py`
2. `app/api/v1/router.py`
3. `tests/integration/test_prep_packages_api.py`

验收标准：

1. 实现 `POST /api/v1/prep-packages`。
2. 实现 `GET /api/v1/prep-packages/{prep_package_id}`。
3. 生成接口同步返回 `prep_package_id`、`agent_run_id`、`status`。
4. 详情接口返回备战总览、JD 拆解、差距分析、题库、手册、推荐先练 3 题、行动清单。
5. 返回结构符合统一 API 响应格式。

测试方式：

1. 调用生成接口，断言状态码 200 或 201。
2. 调用详情接口，断言包含所有核心模块。
3. 查询不存在的备战包，断言返回统一错误格式。

### T026 实现题库查询 API

目标：

支持查询备战包题库，并按模块和难度过滤。

文件路径：

1. `app/api/v1/routes/prep_packages.py`
2. `app/services/question_service.py`
3. `tests/integration/test_questions_api.py`

验收标准：

1. 实现 `GET /api/v1/prep-packages/{prep_package_id}/questions`。
2. 支持 query `module=self_intro|professional|behavior_project`。
3. 支持 query `difficulty=basic|medium|hard`。
4. 返回题目包含 question_text、purpose、difficulty、source_refs、answer_framework、star_template。

测试方式：

1. 查询全部题目，断言不少于 25 道。
2. 按 module 查询，断言题目模块一致。
3. 按 difficulty 查询，断言难度一致。

### T027 实现 Markdown 报告渲染与导出

目标：

将备战包导出为 Markdown 文件。

文件路径：

1. `app/tools/markdown_renderer.py`
2. `app/services/report_service.py`
3. `app/api/v1/routes/reports.py`
4. `app/api/v1/router.py`
5. `tests/integration/test_markdown_export.py`

验收标准：

1. 实现 `POST /api/v1/prep-packages/{prep_package_id}/export/markdown`。
2. Markdown 展示顺序为备战总览、JD 拆解、差距分析、简历建议、准备优先级、题库、手册、先练 3 题、行动清单。
3. 文件写入 `REPORT_DIR`。
4. 文件名包含 `prep_package_id` 和时间戳。
5. 每次导出生成新文件。
6. 更新 `interview_prep_packages.rendered_markdown`。

测试方式：

1. 导出报告，断言返回 `report_path` 和 `markdown`。
2. 检查文件存在且内容非空。
3. 连续导出两次，断言生成两个不同文件。

### T028 实现单题评分服务

目标：

支持题库题目或自定义题目的回答评分。

文件路径：

1. `app/services/evaluation_service.py`
2. `app/agents/answer_evaluator.py`
3. `tests/integration/test_evaluation_service.py`

验收标准：

1. 支持 `question_db_id + user_answer`。
2. 支持 `custom_question_text + user_answer`。
3. 题库题目评分时加载题目、评分锚点、ResumeProfile、JDProfile。
4. 生成 `AnswerEvaluation`。
5. 保存 `answer_evaluations`。
6. 分项评分满分符合 20、25、20、15、10、10。
7. 总分范围为 0 到 100。

测试方式：

1. 对题库题目提交回答，断言保存评分记录。
2. 对自定义题目提交回答，断言保存评分记录。
3. 使用 mock Agent 返回非法分数，断言 Schema 校验失败并重试。

### T029 实现单题评分 API

目标：

提供提交评分、查询评分详情和历史评分接口。

文件路径：

1. `app/api/v1/routes/evaluations.py`
2. `app/api/v1/router.py`
3. `tests/integration/test_evaluations_api.py`

验收标准：

1. 实现 `POST /api/v1/evaluations`。
2. 实现 `GET /api/v1/evaluations/{answer_evaluation_id}`。
3. 实现 `GET /api/v1/evaluations`。
4. 历史查询支持 `prep_package_id`、`question_db_id`、`limit`、`offset`。
5. 响应包含总分、分项评分、优点、改进点、风险、改进版回答、追问、下一题建议、记忆更新建议。

测试方式：

1. 提交评分请求，断言返回 `answer_evaluation_id` 和 `total_score`。
2. 查询评分详情，断言字段完整。
3. 查询历史评分，断言分页参数生效。

### T030 实现记忆写入策略

目标：

根据评分结果生成或更新长期记忆。

文件路径：

1. `app/services/memory_service.py`
2. `app/agents/memory_agent.py`
3. `tests/unit/test_memory_service.py`

验收标准：

1. 高置信度 memory update 自动写入 `memory_items`。
2. 低置信度 update 仅保存在 `answer_evaluations.memory_update_json`。
3. 单次偶然低分不直接写成长期问题。
4. 同类问题连续低分时可写入 active weakness。
5. 记忆包含 evidence、confidence、source_type、source_id。

测试方式：

1. 输入高置信度 weakness，断言写入 memory_items。
2. 输入低置信度 weakness，断言不写入 memory_items。
3. 模拟同类问题连续低分，断言写入 active memory。

### T031 实现 Agent 运行日志查询 API

目标：

支持查看 Agent 运行详情。

文件路径：

1. `app/api/v1/routes/agent_runs.py`
2. `app/services/agent_run_service.py`
3. `app/api/v1/router.py`
4. `tests/integration/test_agent_runs_api.py`

验收标准：

1. 实现 `GET /api/v1/agent-runs/{agent_run_id}`。
2. 返回 run_type、status、prompt_version、steps、error_message。
3. steps 按 `step_order` 排序。
4. 默认不返回完整敏感原文。

测试方式：

1. 查询已存在 agent_run，断言返回步骤列表。
2. 查询不存在的 agent_run，断言统一错误格式。
3. 断言响应不包含完整简历正文。

### T032 准备固定验收样例

目标：

准备 2 到 3 组 MVP 验收样例。

文件路径：

1. `tests/fixtures/sample_cases/backend_java_case.json`
2. `tests/fixtures/sample_cases/backend_python_case.json`
3. `tests/fixtures/sample_cases/backend_go_case.json`

验收标准：

1. 每组样例包含 resume_text、jd_text、可选 experience_text、user_answer。
2. 至少覆盖 Java 或 Python 后端方向。
3. 样例不包含真实个人隐私。
4. 样例可用于备战包生成和单题评分测试。

测试方式：

1. 加载所有 JSON 样例，断言字段完整。
2. 使用样例创建 source documents，断言入库成功。

### T033 编写 Schema 单元测试

目标：

覆盖核心 Schema 约束。

文件路径：

1. `tests/unit/test_common_schemas.py`
2. `tests/unit/test_profile_schemas.py`
3. `tests/unit/test_prep_package_schemas.py`
4. `tests/unit/test_evaluation_memory_schemas.py`

验收标准：

1. 覆盖通用 Schema。
2. 覆盖 ResumeProfile、JDProfile、ExperienceProfile。
3. 覆盖 QuestionBank 数量约束。
4. 覆盖 PrepManual 数量约束。
5. 覆盖 AnswerEvaluation 分数约束。

测试方式：

1. 运行 `uv run pytest tests/unit`。
2. 所有 Schema 测试通过。

### T034 编写 API 集成测试

目标：

覆盖主要 API 的正向和错误路径。

文件路径：

1. `tests/integration/test_documents_api.py`
2. `tests/integration/test_resumes_api.py`
3. `tests/integration/test_jobs_api.py`
4. `tests/integration/test_experiences_api.py`
5. `tests/integration/test_prep_packages_api.py`
6. `tests/integration/test_evaluations_api.py`

验收标准：

1. 覆盖材料创建。
2. 覆盖简历和 JD 创建解析。
3. 覆盖面经创建解析。
4. 覆盖备战包生成和查询。
5. 覆盖单题评分提交和查询。
6. 覆盖统一错误格式。

测试方式：

1. 运行 `uv run pytest tests/integration`。
2. 所有集成测试通过。

### T035 编写端到端 MVP 验收测试

目标：

验证第一阶段 MVP 主闭环完整可用。

文件路径：

1. `tests/e2e/test_mvp_prep_package_flow.py`
2. `tests/e2e/test_mvp_answer_evaluation_flow.py`

验收标准：

1. 文本简历和 JD 可以创建 source document。
2. 简历和 JD 可以创建业务记录。
3. 简历和 JD 可以解析出 profile。
4. 可以生成完整备战包。
5. 备战包包含不少于 25 道题。
6. 可以导出 Markdown 报告。
7. 可以选择一道题提交回答。
8. 可以生成评分报告。
9. 可以查询 Agent 运行日志。
10. 不依赖真实 LLM，使用 mock Agent 也可跑通。

测试方式：

1. 运行 `uv run pytest tests/e2e`。
2. 断言主流程全部通过。
3. 检查测试生成的 Markdown 文件存在且非空。

## 4. 建议执行顺序

第一批任务：

1. T001
2. T002
3. T003
4. T010
5. T014
6. T015

第二批任务：

1. T004
2. T005
3. T006
4. T007
5. T008
6. T009

第三批任务：

1. T011
2. T012
3. T013
4. T019
5. T020
6. T023

第四批任务：

1. T016
2. T017
3. T018
4. T021
5. T022

第五批任务：

1. T024
2. T025
3. T026
4. T027

第六批任务：

1. T028
2. T029
3. T030
4. T031

第七批任务：

1. T032
2. T033
3. T034
4. T035

## 5. MVP 完成判定

MVP 任务完成需要满足：

1. T001 到 T035 全部完成。
2. `uv run pytest tests/unit` 通过。
3. `uv run pytest tests/integration` 通过。
4. `uv run pytest tests/e2e` 通过。
5. 使用 mock Agent 可以完整跑通“输入简历 + JD -> 生成备战包 -> 导出 Markdown -> 提交单题回答 -> 生成评分”的闭环。
6. 代码中没有实现第一阶段明确排除的自动联网搜索、登录注册、支付、实时语音和正式前端。
