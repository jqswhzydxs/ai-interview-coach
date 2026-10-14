# MVP 第一阶段任务拆解：面试问题生成与单题评价 v0.1

## 1. 任务拆解说明

本任务清单对应：

1. `docs/17-mvp-question-generation-and-answer-evaluation-spec-v0.1.md`
2. `docs/18-mvp-question-generation-and-answer-evaluation-plan-v0.1.md`

目标闭环：

```text
输入简历 + JD + 准备目标
↓
生成岗位相关面试问题
↓
提交单题答案
↓
获得结构化评价
```

约束：

1. 使用 mock/stub Agent 先跑通完整闭环。
2. 不实现自动联网搜索、登录注册、正式前端、实时语音、PDF 导出、真实面试复盘、质量评测后台。
3. 不建 `interview_reviews` 和 `quality_evaluations`。
4. 每个任务都必须可单独实现、测试和验收。

## 2. 任务总览

| ID | 任务 | 依赖 |
| --- | --- | --- |
| T001 | 初始化后端项目结构 | 无 |
| T002 | 实现配置、日志、request_id 和健康检查 | T001 |
| T003 | 实现统一响应、错误模型和分页参数 | T002 |
| T004 | 实现文本 hash、脱敏和文件解析工具 | T001 |
| T005 | 配置数据库连接和 Alembic | T002 |
| T006 | 实现 MVP ORM 模型 | T005 |
| T007 | 生成初始迁移并初始化默认用户 | T006 |
| T008 | 实现通用 Pydantic Schema | T001 |
| T009 | 实现 Profile Schema | T008 |
| T010 | 实现题库与备战包 Schema | T008 |
| T011 | 实现单题评价与记忆 Schema | T008 |
| T012 | 实现 Agent 基础设施和 mock LLMClient | T008 |
| T013 | 实现 Harness 和 Agent 运行日志 | T006, T012 |
| T014 | 实现 Prompt 文件与加载器 | T012 |
| T015 | 实现材料保存接口 | T003, T004, T006 |
| T016 | 实现简历创建与解析 | T009, T013, T015 |
| T017 | 实现 JD 创建与解析 | T009, T013, T015 |
| T018 | 实现可选面经创建与解析 | T009, T013, T015 |
| T019 | 实现问题生成 Agent mocks | T010, T013, T016, T017 |
| T020 | 实现备战包生成服务与 API | T019 |
| T021 | 实现题库查询 API | T020 |
| T022 | 实现单题评价 Agent mocks | T011, T013, T020 |
| T023 | 实现单题评价服务与 API | T022 |
| T024 | 实现记忆写入策略 | T011, T023 |
| T025 | 实现 Agent 运行日志查询 API | T013 |
| T026 | 准备固定样例与测试套件 | T015-T025 |
| T027 | 实现端到端验收测试 | T026 |

## 3. 详细任务

### T001 初始化后端项目结构

目标文件：

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
17. `tests/unit/__init__.py`
18. `tests/integration/__init__.py`
19. `tests/e2e/__init__.py`

实现内容：

1. 建立 FastAPI 后端目录结构。
2. 配置 Python 3.11。
3. 使用 `uv + pyproject.toml` 管理依赖。
4. 添加 FastAPI、Uvicorn、SQLAlchemy、Alembic、Pydantic v2、pydantic-settings、psycopg、pytest、httpx、PyMuPDF、python-docx 等依赖。

测试方式：

1. 运行 `uv sync`。
2. 运行 `uv run python --version`。
3. 运行 `uv run python -c "import fastapi, sqlalchemy, pydantic"`。

验收标准：

1. 项目依赖安装成功。
2. Python 版本为 3.11.x。
3. 基础目录存在。
4. 未创建前端、登录注册、支付等非目标目录。

### T002 实现配置、日志、request_id 和健康检查

目标文件：

1. `.env.example`
2. `app/core/config.py`
3. `app/core/logging.py`
4. `app/core/middleware.py`
5. `app/main.py`
6. `app/api/v1/router.py`
7. `app/api/v1/routes/health.py`
8. `tests/integration/test_health.py`

实现内容：

1. 使用 Pydantic Settings 读取配置。
2. 配置 `APP_ENV`、`APP_NAME`、`DATABASE_URL`、`UPLOAD_DIR`、`REPORT_DIR`、`DEFAULT_USER_ID`、`LLM_PROVIDER`、`LLM_MODEL`、`DEEPSEEK_API_KEY`、`KIMI_API_KEY`、`SAVE_FULL_LLM_LOGS`。
3. 实现 request_id 中间件。
4. 实现基础日志配置。
5. 实现 `GET /api/v1/health`。

测试方式：

1. `uv run pytest tests/integration/test_health.py`。
2. 用 TestClient 请求 `/api/v1/health`。

验收标准：

1. `/api/v1/health` 返回 200。
2. 响应包含 `status=ok`。
3. 响应包含 request_id。
4. 日志中可携带 request_id。

### T003 实现统一响应、错误模型和分页参数

目标文件：

1. `app/schemas/response.py`
2. `app/schemas/pagination.py`
3. `app/core/errors.py`
4. `app/main.py`
5. `tests/unit/test_response_schemas.py`
6. `tests/integration/test_error_response.py`

实现内容：

1. 定义统一成功响应结构。
2. 定义统一错误响应结构。
3. 定义错误码：`VALIDATION_ERROR`、`NOT_FOUND`、`AGENT_FAILED`、`INTERNAL_ERROR`。
4. 定义 `limit + offset` 分页参数。
5. 注册全局异常处理器。

测试方式：

1. 单元测试校验响应 Schema。
2. 集成测试发送非法请求，检查错误格式。

验收标准：

1. 成功响应格式统一为 `data/message/request_id`。
2. 错误响应格式统一为 `error.code/error.message/error.details`。
3. 分页 `limit` 有默认值和最大值。

### T004 实现文本 hash、脱敏和文件解析工具

目标文件：

1. `app/tools/text_utils.py`
2. `app/tools/file_parser.py`
3. `tests/unit/test_text_utils.py`
4. `tests/unit/test_file_parser.py`
5. `tests/fixtures/files/sample_resume.txt`
6. `tests/fixtures/files/sample_resume.md`
7. `tests/fixtures/files/sample_resume.docx`
8. `tests/fixtures/files/sample_resume.pdf`

实现内容：

1. 实现 SHA-256 文本 hash。
2. 实现手机号脱敏。
3. 实现邮箱脱敏。
4. 支持纯文本、Markdown、DOCX、PDF 解析。
5. 文件大小限制 5MB。
6. 不支持类型返回明确错误。

测试方式：

1. `uv run pytest tests/unit/test_text_utils.py`。
2. `uv run pytest tests/unit/test_file_parser.py`。

验收标准：

1. 同一文本 hash 稳定一致。
2. 手机号和邮箱可被脱敏。
3. 四类样例文件可解析出文本。
4. 超过 5MB 或非法类型会失败。

### T005 配置数据库连接和 Alembic

目标文件：

1. `app/db/base.py`
2. `app/db/session.py`
3. `app/db/deps.py`
4. `alembic.ini`
5. `alembic/env.py`
6. `alembic/versions/.gitkeep`
7. `tests/unit/test_db_config.py`

实现内容：

1. 配置 SQLAlchemy engine。
2. 配置 `SessionLocal`。
3. 实现 FastAPI DB dependency。
4. 配置 Alembic 读取 ORM metadata 和 `DATABASE_URL`。

测试方式：

1. `uv run pytest tests/unit/test_db_config.py`。
2. `uv run alembic current`。

验收标准：

1. DB 配置可从环境变量读取。
2. Alembic 可加载项目 metadata。
3. session dependency 可正常创建和关闭 session。

### T006 实现 MVP ORM 模型

目标文件：

1. `app/db/models/user.py`
2. `app/db/models/source_document.py`
3. `app/db/models/resume.py`
4. `app/db/models/job_description.py`
5. `app/db/models/interview_experience.py`
6. `app/db/models/prep_package.py`
7. `app/db/models/question.py`
8. `app/db/models/evaluation.py`
9. `app/db/models/memory.py`
10. `app/db/models/agent_run.py`
11. `app/db/models/__init__.py`
12. `tests/unit/test_models_metadata.py`

实现内容：

1. 实现 `users`。
2. 实现 `source_documents`。
3. 实现 `resumes` / `resume_profiles`。
4. 实现 `job_descriptions` / `jd_profiles`。
5. 实现 `interview_experiences` / `experience_profiles`。
6. 实现 `interview_prep_packages`、`prep_package_experiences`、`match_reports`、`interview_questions`、`recommended_questions`。
7. 实现 `answer_evaluations`。
8. 实现 `memory_items`。
9. 实现 `agent_runs`、`agent_run_steps`。
10. 不实现 `interview_reviews` 和 `quality_evaluations`。

测试方式：

1. `uv run pytest tests/unit/test_models_metadata.py`。
2. 检查 metadata 表名。

验收标准：

1. MVP 必需表都在 ORM metadata 中。
2. 不包含 `interview_reviews` 和 `quality_evaluations`。
3. 核心外键关系存在。
4. JSONB 字段用于保存 Agent 结构化输出。

### T007 生成初始迁移并初始化默认用户

目标文件：

1. `alembic/versions/*_initial_mvp_schema.py`
2. `app/db/init_db.py`
3. `app/main.py`
4. `tests/integration/test_migrations.py`
5. `tests/integration/test_default_user.py`

实现内容：

1. 生成初始 Alembic migration。
2. 实现应用启动时创建默认用户。
3. 默认用户 ID 来自 `DEFAULT_USER_ID`。
4. 默认用户 role 为 `candidate`。

测试方式：

1. `uv run alembic upgrade head`。
2. `uv run pytest tests/integration/test_migrations.py`。
3. `uv run pytest tests/integration/test_default_user.py`。

验收标准：

1. 迁移可执行。
2. 默认用户可自动创建。
3. 重复启动不会重复创建默认用户。

### T008 实现通用 Pydantic Schema

目标文件：

1. `app/schemas/common.py`
2. `tests/unit/test_common_schemas.py`

实现内容：

1. 实现 `EvidenceRef`。
2. 实现 `ScoreItem`。
3. 实现 `ActionItem`。
4. 实现 Agent 输出元信息基类。

测试方式：

1. `uv run pytest tests/unit/test_common_schemas.py`。

验收标准：

1. `source_type` 枚举校验生效。
2. `ScoreItem.score <= max_score`。
3. `ActionItem.priority` 只允许 `high/medium/low`。

### T009 实现 Profile Schema

目标文件：

1. `app/schemas/resume.py`
2. `app/schemas/job_description.py`
3. `app/schemas/experience.py`
4. `tests/unit/test_profile_schemas.py`

实现内容：

1. 实现 `ResumeProfile`。
2. 实现 `JDProfile`。
3. 实现 `ExperienceProfile`。
4. 支持 `schema_version/generated_at/agent_name/prompt_version`。

测试方式：

1. `uv run pytest tests/unit/test_profile_schemas.py`。

验收标准：

1. 合法简历画像可通过校验。
2. 合法 JD 画像可通过校验。
3. 合法面经画像可通过校验。
4. 缺失关键字段会失败。

### T010 实现题库与备战包 Schema

目标文件：

1. `app/schemas/question.py`
2. `app/schemas/prep_package.py`
3. `tests/unit/test_question_bank_schemas.py`
4. `tests/unit/test_prep_package_schemas.py`

实现内容：

1. 实现 `MatchReport`。
2. 实现 `InterviewQuestion`。
3. 实现 `QuestionBank`。
4. 实现 `RecommendedQuestion`。
5. 实现 `InterviewPrepPackage`。

测试方式：

1. `uv run pytest tests/unit/test_question_bank_schemas.py`。
2. `uv run pytest tests/unit/test_prep_package_schemas.py`。

验收标准：

1. 题库不少于 25 道。
2. 三个模块每个不少于 8 道。
3. `question_id` 唯一。
4. 每题必须有来源依据和评分锚点。
5. 24 道题样例校验失败。

### T011 实现单题评价与记忆 Schema

目标文件：

1. `app/schemas/evaluation.py`
2. `app/schemas/memory.py`
3. `app/schemas/agent.py`
4. `tests/unit/test_evaluation_schemas.py`
5. `tests/unit/test_memory_schemas.py`

实现内容：

1. 实现 `AnswerEvaluation`。
2. 实现分项评分结构。
3. 实现 `MemoryItem`。
4. 实现 Agent run / step 响应 Schema。

测试方式：

1. `uv run pytest tests/unit/test_evaluation_schemas.py`。
2. `uv run pytest tests/unit/test_memory_schemas.py`。

验收标准：

1. 总分范围 0 到 100。
2. 各分项不超过对应满分。
3. 至少 1 条改进建议。
4. 至少 1 个追问。
5. 非法 memory status 校验失败。

### T012 实现 Agent 基础设施和 mock LLMClient

目标文件：

1. `app/agents/base.py`
2. `app/agents/llm_client.py`
3. `app/agents/mock_client.py`
4. `app/agents/deepseek_client.py`
5. `app/agents/kimi_client.py`
6. `tests/unit/test_llm_client.py`

实现内容：

1. 定义 Agent 基类。
2. 定义 `LLMClient` 抽象。
3. 实现 `MockLLMClient`。
4. 提供 DeepSeek Provider 骨架。
5. 提供 Kimi Provider 骨架。
6. 支持 `LLM_PROVIDER=mock|deepseek|kimi`。

测试方式：

1. `uv run pytest tests/unit/test_llm_client.py`。

验收标准：

1. mock provider 可返回固定输出。
2. 非法 provider 返回明确错误。
3. 业务层不直接调用 DeepSeek/Kimi SDK 或 HTTP。

### T013 实现 Harness 和 Agent 运行日志

目标文件：

1. `app/agents/harness.py`
2. `app/services/agent_run_service.py`
3. `tests/unit/test_harness.py`

实现内容：

1. 创建 `agent_runs`。
2. 创建 `agent_run_steps`。
3. 调用 Agent。
4. 校验 Agent 输出 Schema。
5. 校验失败自动重试一次。
6. 保存输入输出摘要。
7. 失败时记录错误并返回 `AGENT_FAILED`。

测试方式：

1. `uv run pytest tests/unit/test_harness.py`。

验收标准：

1. 成功运行写入 run 和 step。
2. 失败运行状态为 `failed`。
3. Schema 校验失败会重试一次。
4. 默认不保存完整敏感原文。

### T014 实现 Prompt 文件与加载器

目标文件：

1. `app/agents/prompt_loader.py`
2. `app/agents/prompts/resume_analyzer_v0.1.md`
3. `app/agents/prompts/jd_analyzer_v0.1.md`
4. `app/agents/prompts/experience_analyzer_v0.1.md`
5. `app/agents/prompts/matching_agent_v0.1.md`
6. `app/agents/prompts/question_bank_agent_v0.1.md`
7. `app/agents/prompts/answer_evaluator_v0.1.md`
8. `app/agents/prompts/memory_agent_v0.1.md`
9. `tests/unit/test_prompt_loader.py`

实现内容：

1. 为每个 Agent 创建 Prompt 文件。
2. Prompt 包含不编造经历、不联网搜索、面经只作参考、材料不足标注综合推断等边界。
3. 实现按名称和版本加载 Prompt。

测试方式：

1. `uv run pytest tests/unit/test_prompt_loader.py`。

验收标准：

1. 所有 Prompt 文件可加载。
2. 缺失 Prompt 返回明确错误。
3. Prompt 文件名包含版本号。

### T015 实现材料保存接口

目标文件：

1. `app/api/v1/routes/documents.py`
2. `app/services/document_service.py`
3. `app/api/v1/router.py`
4. `tests/integration/test_documents_api.py`

实现内容：

1. 实现 `POST /api/v1/documents/text`。
2. 实现 `POST /api/v1/documents/upload`。
3. 支持 `resume`、`jd`、`interview_experience`。
4. 保存 `source_documents`。
5. 保存 `raw_text`、`text_hash`、metadata、file_path。

测试方式：

1. `uv run pytest tests/integration/test_documents_api.py`。

验收标准：

1. 文本简历可保存。
2. 文本 JD 可保存。
3. 可选面经可保存。
4. 上传文件可保存并解析。
5. 不自动联网搜索。

### T016 实现简历创建与解析

目标文件：

1. `app/api/v1/routes/resumes.py`
2. `app/services/resume_service.py`
3. `app/agents/resume_analyzer.py`
4. `app/api/v1/router.py`
5. `tests/integration/test_resumes_api.py`

实现内容：

1. 实现 `POST /api/v1/resumes`。
2. 实现 `POST /api/v1/resumes/{resume_id}/parse`。
3. 使用 Harness 调用 Resume Analyzer mock。
4. 保存 `resume_profiles`。

测试方式：

1. `uv run pytest tests/integration/test_resumes_api.py`。

验收标准：

1. 简历记录可创建。
2. 简历可解析为 `ResumeProfile`。
3. 返回 `resume_profile_id` 和 `agent_run_id`。
4. Agent run 和 step 被记录。

### T017 实现 JD 创建与解析

目标文件：

1. `app/api/v1/routes/jobs.py`
2. `app/services/job_service.py`
3. `app/agents/jd_analyzer.py`
4. `app/api/v1/router.py`
5. `tests/integration/test_jobs_api.py`

实现内容：

1. 实现 `POST /api/v1/jobs`。
2. 实现 `POST /api/v1/jobs/{job_description_id}/parse`。
3. 使用 Harness 调用 JD Analyzer mock。
4. 保存 `jd_profiles`。

测试方式：

1. `uv run pytest tests/integration/test_jobs_api.py`。

验收标准：

1. JD 记录可创建。
2. JD 可解析为 `JDProfile`。
3. 返回 `jd_profile_id` 和 `agent_run_id`。
4. Agent run 和 step 被记录。

### T018 实现可选面经创建与解析

目标文件：

1. `app/api/v1/routes/experiences.py`
2. `app/services/experience_service.py`
3. `app/agents/experience_analyzer.py`
4. `app/api/v1/router.py`
5. `tests/integration/test_experiences_api.py`

实现内容：

1. 实现 `POST /api/v1/experiences`。
2. 实现 `POST /api/v1/experiences/{interview_experience_id}/parse`。
3. 使用 Harness 调用 Experience Analyzer mock。
4. 保存 `experience_profiles`。

测试方式：

1. `uv run pytest tests/integration/test_experiences_api.py`。

验收标准：

1. 面经可创建。
2. 面经可解析为 `ExperienceProfile`。
3. 没有面经时不影响题库生成流程。

### T019 实现问题生成 Agent mocks

目标文件：

1. `app/agents/matching_agent.py`
2. `app/agents/question_bank_agent.py`
3. `tests/unit/test_question_generation_agents.py`

实现内容：

1. Matching Agent mock 输出合法 `MatchReport`。
2. Question Bank Agent mock 输出合法 `QuestionBank`。
3. mock 题库包含不少于 25 道题。
4. 三个模块每个不少于 8 道。
5. 每题包含来源依据和评分锚点。

测试方式：

1. `uv run pytest tests/unit/test_question_generation_agents.py`。

验收标准：

1. mock `MatchReport` 通过 Schema 校验。
2. mock `QuestionBank` 通过 Schema 校验。
3. 24 道题 mock 会失败。

### T020 实现备战包生成服务与 API

目标文件：

1. `app/services/prep_package_service.py`
2. `app/api/v1/routes/prep_packages.py`
3. `app/api/v1/router.py`
4. `tests/integration/test_prep_packages_api.py`

实现内容：

1. 实现 `POST /api/v1/prep-packages`。
2. 请求支持 `resume_id`、`job_description_id`、可选 `interview_experience_ids`、`preparation_goal`、`title`。
3. `preparation_goal` 写入 `agent_runs.input_summary_json` 和 `interview_prep_packages.overview_json`。
4. 生成并保存 `match_reports`。
5. 生成并保存 `interview_questions`。
6. 生成并保存 `recommended_questions`。
7. 同步返回 `prep_package_id`、`agent_run_id`、`status`。

测试方式：

1. `uv run pytest tests/integration/test_prep_packages_api.py`。

验收标准：

1. 给定简历和 JD 可以生成备战包。
2. 备战包状态为 `ready`。
3. 题库不少于 25 道。
4. 推荐题为 3 道。
5. 准备目标被保存到 overview 或 input summary。

### T021 实现题库查询 API

目标文件：

1. `app/services/question_service.py`
2. `app/api/v1/routes/prep_packages.py`
3. `tests/integration/test_questions_api.py`

实现内容：

1. 实现 `GET /api/v1/prep-packages/{prep_package_id}`。
2. 实现 `GET /api/v1/prep-packages/{prep_package_id}/questions`。
3. 支持 `module` 过滤。
4. 支持 `difficulty` 过滤。

测试方式：

1. `uv run pytest tests/integration/test_questions_api.py`。

验收标准：

1. 可查询备战包详情。
2. 可查询全部题目。
3. 按模块过滤结果正确。
4. 按难度过滤结果正确。

### T022 实现单题评价 Agent mocks

目标文件：

1. `app/agents/answer_evaluator.py`
2. `app/agents/memory_agent.py`
3. `tests/unit/test_answer_evaluation_agents.py`

实现内容：

1. Answer Evaluator mock 输出合法 `AnswerEvaluation`。
2. Memory Agent mock 输出 memory update 建议。
3. mock 评分包含总分、分项分、扣分原因、改进版回答、追问、下一题建议。

测试方式：

1. `uv run pytest tests/unit/test_answer_evaluation_agents.py`。

验收标准：

1. mock `AnswerEvaluation` 通过 Schema 校验。
2. 分项分不超过满分。
3. 至少有 1 条改进建议。
4. 至少有 1 个追问。

### T023 实现单题评价服务与 API

目标文件：

1. `app/services/evaluation_service.py`
2. `app/api/v1/routes/evaluations.py`
3. `app/api/v1/router.py`
4. `tests/integration/test_evaluations_api.py`

实现内容：

1. 实现 `POST /api/v1/evaluations`。
2. 支持 `question_db_id + user_answer`。
3. 支持 `custom_question_text + user_answer`。
4. 题库题目评分时加载题目、评分锚点、ResumeProfile、JDProfile。
5. 保存 `answer_evaluations`。
6. 实现 `GET /api/v1/evaluations/{answer_evaluation_id}`。
7. 实现 `GET /api/v1/evaluations`。

测试方式：

1. `uv run pytest tests/integration/test_evaluations_api.py`。

验收标准：

1. 题库题目答案可评分。
2. 自定义题目答案可评分。
3. 返回 `answer_evaluation_id` 和总分。
4. 查询详情字段完整。
5. 历史查询支持分页。

### T024 实现记忆写入策略

目标文件：

1. `app/services/memory_service.py`
2. `tests/unit/test_memory_service.py`

实现内容：

1. 高置信度 memory update 写入 `memory_items`。
2. 低置信度 memory update 只保存在 `answer_evaluations.memory_update_json`。
3. 单次偶然低分不直接写成长期问题。
4. 记忆包含 evidence、confidence、source_type、source_id。

测试方式：

1. `uv run pytest tests/unit/test_memory_service.py`。

验收标准：

1. 高置信度记忆可入库。
2. 低置信度记忆不入库。
3. 记忆来源可追溯到评分记录。

### T025 实现 Agent 运行日志查询 API

目标文件：

1. `app/api/v1/routes/agent_runs.py`
2. `app/services/agent_run_service.py`
3. `app/api/v1/router.py`
4. `tests/integration/test_agent_runs_api.py`

实现内容：

1. 实现 `GET /api/v1/agent-runs/{agent_run_id}`。
2. 返回 run_type、status、prompt_version、steps、error_message。
3. steps 按 `step_order` 排序。
4. 默认不返回完整敏感原文。

测试方式：

1. `uv run pytest tests/integration/test_agent_runs_api.py`。

验收标准：

1. 可查询 Agent run。
2. 可查看步骤列表。
3. 不存在的 run 返回 `NOT_FOUND`。
4. 响应不包含完整简历正文。

### T026 准备固定样例与测试套件

目标文件：

1. `tests/fixtures/sample_cases/backend_java_case.json`
2. `tests/fixtures/sample_cases/backend_python_case.json`
3. `tests/fixtures/sample_cases/backend_go_case.json`
4. `tests/unit/test_schema_constraints.py`
5. `tests/integration/test_mvp_api_flow.py`

实现内容：

1. 准备 2 到 3 组固定样例。
2. 每组包含 resume_text、jd_text、preparation_goal、可选 experience_text、user_answer。
3. 样例不包含真实隐私。
4. 单元测试覆盖 Schema 约束。
5. 集成测试覆盖 API 主路径。

测试方式：

1. `uv run pytest tests/unit/test_schema_constraints.py`。
2. `uv run pytest tests/integration/test_mvp_api_flow.py`。

验收标准：

1. 样例可被加载。
2. 题库数量约束被测试覆盖。
3. 评分维度约束被测试覆盖。
4. API 主路径可跑通。

### T027 实现端到端验收测试

目标文件：

1. `tests/e2e/test_question_generation_and_evaluation_flow.py`

实现内容：

端到端测试以下流程：

```text
POST /api/v1/documents/text 创建简历材料
POST /api/v1/documents/text 创建 JD 材料
POST /api/v1/resumes 创建简历
POST /api/v1/jobs 创建 JD
POST /api/v1/resumes/{id}/parse
POST /api/v1/jobs/{id}/parse
POST /api/v1/prep-packages 生成题库
GET /api/v1/prep-packages/{id}/questions 查询题库
POST /api/v1/evaluations 提交答案
GET /api/v1/evaluations/{id} 查询评价
GET /api/v1/agent-runs/{id} 查询日志
```

测试方式：

1. `uv run pytest tests/e2e/test_question_generation_and_evaluation_flow.py`。

验收标准：

1. mock Agent 可跑通完整闭环。
2. 题库不少于 25 道。
3. 三个模块每个不少于 8 道。
4. 推荐题数量为 3。
5. 单题评价总分在 0 到 100。
6. 分项评分不超过各自满分。
7. 改进版回答存在。
8. 至少有 1 个追问。
9. Agent run 和 step 可查询。

## 4. 推荐执行顺序

第一批：

1. T001
2. T002
3. T003
4. T004
5. T008

第二批：

1. T005
2. T006
3. T007

第三批：

1. T009
2. T010
3. T011
4. T012
5. T013
6. T014

第四批：

1. T015
2. T016
3. T017
4. T018

第五批：

1. T019
2. T020
3. T021

第六批：

1. T022
2. T023
3. T024
4. T025

第七批：

1. T026
2. T027

## 5. 完成判定

本任务集完成时，应满足：

1. T001 到 T027 全部完成。
2. `uv run pytest tests/unit` 通过。
3. `uv run pytest tests/integration` 通过。
4. `uv run pytest tests/e2e` 通过。
5. 使用 mock Agent 可完整跑通“输入简历 + JD + 准备目标 -> 生成题库 -> 提交答案 -> 获得结构化评价”。
6. 未实现自动联网搜索、登录注册、正式前端、真实语音、PDF 导出、真实面试复盘和质量评测后台。
